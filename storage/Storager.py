import random
import threading
from multiprocessing import Process
from typing import List

import pandas as pd
from django.contrib.messages.constants import SUCCESS

from logger.logger import logWriter as log
from paradigm.channel import Channel
from paradigm.model import ModelFormatOutput
from paradigm.replicate import ChunkReplicateRecord, ReplicateState
from paradigm.slot import CommitSlotItem
from paradigm.storage import ErasureCodeChunks, ErasureCodeChunk, ErasureCodeRecoverError, ReplicateChunk
from storage.chunker.chunker import Chunker
from storage.encoder.rs_decoder import ReedSolomonDecoder
from storage.encoder.rs_encoder import ReedSolomonEncoder
from utils.cryptography.commitment.kzg.kzg_commitment import KZGCommitment, KZGProof
from utils.cryptography.hash.hasher import Hasher

"""
    NOTE: Storager 2024-12-31 14:13 Version 0.1
    # 1. 将输出ModelFormatOutput.output中的数据部分计算commitment
        1.1 这里的commitment针对数据本身，以dataframe为例，按num_row_per_chunk分为若干个chunk,为这些chunk计算一个commitment(e.g. merkle root)
        1.2 节点在收到commitment后，可以验证自己的那部分chunk是否属于整个commitment(计算一遍哈希)，从而向Master投票说明commitment的准确性
        1.3 commitment会用于zkp的生成
    # 2. 分块并生成纠删码并完成分发
        2.1 这里纠删码暂时定为,为1中每个chunk生成纠删码冗余块，然后将每个chunk的k个块发送给节点，这样每个节点需要k/n的带宽
        2.2 节点收到k个块后还原出整个文件，然后计算各个部分的hash，并验证commitment和相关的proof（这里计算量可能有点大，后面再考虑初步先实现一个版本v0.1）
        2.3 验证成功后，节点存储每个chunk的特定一个块到本地，这样每个节点一共存了nb_chunk个块，这里投票要附带自己存的各个chunk的索引
    # 3. 存储收到的冗余数据块（包括自己的）
"""


class Storager:
    def __init__(self, channel: Channel):
        # 这里还需要提供一个索引，用于索引存了哪些冗余块，各个冗余数据块存在哪里，暂时先不管（这里是否应该是在layer2node里存？）
        # 另外，冗余数据块索引还需要进行持久化，不然down了就没有索引了，用追加日志的方式 todo
        self.index = {}
        self.channel: Channel = channel
        self.pending_slot_waiting_record = {} # 这里要记录那些在grpc转发的slot，等待返回的record
    def process_pending_slots_to_undetermined(self):
        # 这里是slot的一个特殊中间状态，已经被storager生成好了ec chunks，并且发送给了grpc
        # 正在等待grpc转发结果，如果转发成功，那么可以转给slotManager，反之说明纠删码的参数需要调整 todo
        while True:
            if self.channel.to_storager_record_channel.empty():
                continue
            try:
                iter_chunk_replicate_record: ChunkReplicateRecord = self.channel.to_storager_record_channel.get(timeout=0.01)
                if iter_chunk_replicate_record.check() != ReplicateState.SUCCESS:
                    # 没有转发成功，这里暂时处理为直接报错 todo @YZM
                    raise ValueError("EC Params should be justified...")
                if not self.pending_slot_waiting_record.get(iter_chunk_replicate_record.slot_hash):
                    raise ValueError("{} does not been pending in Storager!!!".format(iter_chunk_replicate_record.slot_hash))
                slot: CommitSlotItem = self.pending_slot_waiting_record[iter_chunk_replicate_record.slot_hash]
                slot.update_record(iter_chunk_replicate_record)
                self.pending_slot_waiting_record[iter_chunk_replicate_record.slot_hash] = slot
                if slot.check_replicate_state():
                    slot.sign_as_processed()
                    del self.pending_slot_waiting_record[iter_chunk_replicate_record.slot_hash]
                    self.channel.to_slot_manager_channel.put(slot)
                    log.write_log("STORAGE", "finish replicate the data from Task {} Slot {}".format(slot.sign, slot.slot))
            except Exception as e:
                    raise RuntimeError(e)

    def process_unprocess_slots_to_pending(self):
        while True:
            # Get a task from the task pool (blocking)
            if self.channel.to_storager_slot_channel.empty():
                continue
            try:
                packed_slot_output = self.channel.to_storager_slot_channel.get(timeout=1)
                slot: CommitSlotItem = packed_slot_output[0]
                output: ModelFormatOutput = packed_slot_output[1]
                # commitment = self.compute_model_output_commitment(output) # 计算输出文件的承诺（和ec无关）
                commitment = self.process_unprocess_slot(slot, output.output) # 这里要完成全部的任务： 1. commitment的计算; 2. 分发
                slot.set_commitment(commitment)
                # 数据块已经备份，可恢复,将状态置为UNDETERMINED，然后交还给slotManager
                # self.channel.to_slot_manager_channel.put(slot)
                # 这里将slot标记为pending，等待转发结果
                # self.finish_task_pool.put(FinishTaskPoolItem(task_data, commitment))
            except Exception as e:
                raise RuntimeError(e)
    def process_unprocess_slot(self, slot: CommitSlotItem, output):
        # 计算output的commitment
        # todo 这里应该是先分块，然后计算commitment，然后用ec，这里框架要修改，暂时先跑通原状 @YZM
        hasher = Hasher()
        chunker = Chunker(hasher=hasher)
        chunks, commitment = chunker.chunk(output) # 对输出进行分块，得到chunks和commitment
        # 得到每个chunk的merkle proof
        merkle_proofs = [commitment.open(chunk) for chunk in chunks]
        ec_encoder = ReedSolomonEncoder()
        encoded_packed_chunks:List[ErasureCodeChunks] = [ec_encoder.encode(chunk) for chunk in chunks] # 对每个分块进行ec冗余，这里每一个chunk是ErasureCodeChunks
        replicate_encode_chunks = []
        # TODO @YZM 这里先写成把每个chunk分开来发，后面要改成每个节点一下子发k块
        # 这里单独只给一个块的话，节点无法恢复行块，也就无法判断数据的commitment proof是否正确，因此需要将kzg commitment和merkle proof以及k块数据都发过去 todo
        slot.set_nb_chunks(len(encoded_packed_chunks))
        self.pending_slot_waiting_record[slot.hash] = slot
        # print(self.pending_slot_waiting_record.get(slot.hash), slot.hash)
        for (row, item) in enumerate(encoded_packed_chunks):
            item_kzg_commitment = item.kzg_commitment
            local_index = random.randint(0, len(item.encoded_chunks) - 1)
            # todo 这里的逻辑需要考量 现在只是简单实现
            for (col, chunk) in enumerate(item.encoded_chunks):
                if col == local_index:
                    self.store_local(slot.sign, slot.slot, item.encoded_chunks[col], slot.hash, row, col)
                else:
                    # todo 这里需要k个kzg Proof，发送k个块和这一行的merkle proof
                    kzg_proof = item_kzg_commitment.open(chunk.chunk)
                    replicate_encode_chunk = ReplicateChunk(sign=slot.sign, slot=slot.slot, row_index=row, col_index=col, slot_hash=slot.hash, chunk=chunk.chunk)
                    replicate_encode_chunk.set_kzg_proof(proof=kzg_proof)
                    replicate_encode_chunks.append(replicate_encode_chunk)
                    # send_indices.append(i)
                    # send_chunks.append(item.encoded_chunks[i].chunk)
            # self.grpc_engine.replicate_encoded_chunks(slot.sign, slot.slot,send_chunks, send_indices, item.padding_size, False)
            record = ChunkReplicateRecord(slot_hash=slot.hash, index=row, nb_chunk=len(replicate_encode_chunks), merkle_proof= merkle_proofs[row],padding_size=item.padding_size)
            self.channel.to_grpc_replicate_channel.put((record, replicate_encode_chunks))

        # 这里为了测试collect,将slot和output传递到MockerCollector
        self.channel.test_collect_output_channel.put((slot, output, len(encoded_packed_chunks)))
        log.write_log("STORAGE", "finish pass the data from Task {} Slot {} to grpc_engine".format(slot.sign, slot.slot))
        return commitment


    # store_local 将分块存在本地，构建一个新的ReplicateChunk
    def store_local(self, sign, slot, chunk: ErasureCodeChunk, slot_hash, row_index, col_index):
        local_replicate_chunk = ReplicateChunk(sign, slot, row_index, col_index, slot_hash, chunk=chunk.chunk)
        self.channel.to_receiver_chunk_store_channel.put(local_replicate_chunk) # 交给receiver处理


    # todo 同上
    # 这里读出chunk的内容，自己先检查一遍完整性（其实也不需要，外面可能还要检查一遍？）
    def load_local(self, slot_hash, row_index):
        self.channel.to_receiver_chunk_load_channel.put((slot_hash, row_index)) # 这里暂时先这样写 todo
        # return self.receiver.process_chunk_to_load(slot_hash=slot_hash, row_index=row_index)

    def start(self):
        # TODO 这里还有接收其它块的逻辑
        process_1 = threading.Thread(target=self.process_unprocess_slots_to_pending)
        process_2 = threading.Thread(target=self.process_pending_slots_to_undetermined)
        process_1.start()
        process_2.start()

    # def set_grpc(self, grpc_engine):
    #     self.grpc_engine = grpc_engine



    # 模拟下一个collect的过程，为了拿到本地的就在这边简单模拟下
    # 模拟下要收集这个节点在sign slot里合成的数据块
    def test_collect_process(self, slot_hash, row_index, padding_size)->ErasureCodeChunks:
        # chunks:ErasureCodeChunks  = self.grpc_engine.start_test_collect_process(slot_hash=slot_hash, row_index=row_index, padding_size=padding_size)
        # return chunks
        pass

    def test_recover(self, output, slot_hash, records:List[ChunkReplicateRecord]):
        restored_test_data_merge = pd.DataFrame()

        # todo 这里不考虑排序
        for (row_index, record) in enumerate(records):
            local_chunk = self.load_local(slot_hash, row_index)
            chunks: ErasureCodeChunks =  self.test_collect_process(slot_hash, row_index, record.padding_size)
            chunks.add_chunk(local_chunk)
            decoder = ReedSolomonDecoder()
            restored_test_data, error = decoder.decode(chunks)
            if error != ErasureCodeRecoverError.NONE:
                raise ValueError("ERROR", "Recover data error: {}".format(error.name))

            restored_test_data_merge= pd.concat([restored_test_data_merge, restored_test_data], axis=0, ignore_index=True)
        pd.testing.assert_frame_equal(restored_test_data_merge, output, check_dtype=False, obj="Decoded Dataframe does not match the origin Dataframe")