"""
    NOTE: SimpleReceiver
    Receiver的主要功能是，收集来自节点（包括自己）的数据块，按照既定规则存在本地，并记录相关索引
"""
import os
import threading
from multiprocessing import Process, Queue, Manager
from typing import List

from config.config import BHExecutionNodeGlobalConfig
from paradigm.channel import Channel
from paradigm.replicate import ReplicatePackage
from paradigm.storage import StoredChunk, ErasureCodeChunk, ReplicateChunk, ErasureCodeChunks, ErasureCodeRecoverError
from storage.encoder.rs_decoder import ReedSolomonDecoder
from utils.cryptography.commitment.kzg.kzg_commitment import KZGProof
from utils.cryptography.commitment.merkle.merkle_root import MerkleProof
from utils.cryptography.hash.hasher import HashFunction
from utils.function.func import get_project_root
from logger.logger import logWriter as log

class SimpleReceiver:
    def __init__(self, channel: Channel):
        self.storage_path = os.path.join(get_project_root(), BHExecutionNodeGlobalConfig.STORAGE_PATH) # 存储冗余数据块的路径
        log.write_log("INFO", "Init Storage Receiver from config, storage_path: {}".format(self.storage_path))
        # self.store_chunks: dict = {} # 存储 chunk，通过 slot_hash作为 key
        # self.store_chunk_channel = store_chunk_channel # 通过这一通道传递要存储的 slot
        self.channel = channel


    def process_chunk_to_store(self, sign, slot, slot_hash, row_index, chunk_to_store: ReplicateChunk):
        # ec_chunk里index代表索引，chunk是具体的 bytes
        # 索引可以不记录在文件里，就单纯的记录在这里Receiver里，一旦节点崩溃，重启以后可以通过向 Master询问自己是第几个 # TODO @YZM 这个要在 master里加上
        new_store_chunk_item = StoredChunk(sign=sign, slot=slot, slot_hash=slot_hash, row_index=row_index, storage_path=self.storage_path, chunk_to_store=chunk_to_store)
        data_bytes = chunk_to_store.bytes() # 这里表示纠删码的冗余数据块，bytes直接落盘
        new_store_chunk_item.store(data_bytes) # 存储纠删码
        self.channel.update_store_chunk(slot_hash=slot_hash, new_store_chunk_item=new_store_chunk_item, row_index=row_index)
        # if not self.channel.store_chunks.get(chunk_to_store.slot_hash):
        #     self.channel.store_chunks[chunk_to_store.slot_hash] = Manager.dict()
        # self.channel.store_chunks[chunk_to_store.slot_hash][chunk_to_store.row_index] = new_store_chunk_item
    def process_chunk_to_load(self, slot_hash, row_index)->ErasureCodeChunk:
        # 读取根据 slot_hash来读取
        if not self.channel.store_chunks.get(slot_hash):
            raise ValueError("{} Chunk does not store in this node!!!".format(slot_hash))
        # slot_chunks = self.channel.store_chunks[slot_hash]
        if not self.channel.store_chunks[slot_hash].get(row_index):
            raise ValueError("{} Chunk does not store {} chunk in this node!!!".format(slot_hash, row_index))
        store_chunk_item: StoredChunk = self.channel.store_chunks[slot_hash][row_index]
        chunk = store_chunk_item.load()
        ec_chunk = ErasureCodeChunk(chunk, store_chunk_item.col_index)
        return ec_chunk
    def process_chunk_to_load_without_row_index(self, slot_hash)->List[ErasureCodeChunk]:
        # 读取根据 slot_hash来读取
        chunks = []
        if not self.channel.store_chunks.get(slot_hash):
            raise ValueError("{} Chunk does not store in this node!!!".format(slot_hash))
        # slot_chunks = dict(self.channel.store_chunks[slot_hash])
        for row_index, store_chunk_item in self.channel.store_chunks[slot_hash].items():
            chunk = store_chunk_item.load()
            ec_chunk = ErasureCodeChunk(bytes(chunk), int(store_chunk_item.col_index))
            chunks.append(ec_chunk)
        print(len(chunks))
        return chunks
    def process_chunks_to_store(self):
        while True:
            # Get a task from the task pool (blocking)
            if self.channel.to_receiver_chunk_store_channel.empty():
                continue
            try:
                replicate_package: ReplicatePackage = self.channel.to_receiver_chunk_store_channel.get(timeout=0.01)
                # 首先验证 package的各个 commitment
                chunks = replicate_package.chunks
                kzg_commitment = replicate_package.kzg_commitment
                ec_chunks: ErasureCodeChunks = ErasureCodeChunks(padding_size=replicate_package.padding_size)
                # 验证每个 chunk的 kzg
                for replicate_chunk in chunks:
                    # kzg_proof: KZGProof = replicate_chunk.kzg_proof
                    # if kzg_proof.verify(replicate_chunk.bytes()) and kzg_proof.commitment == kzg_commitment:
                    ec_chunks.add_chunk(ErasureCodeChunk(chunk=replicate_chunk.chunk, index=replicate_chunk.col_index))
                if ec_chunks.check() == ErasureCodeRecoverError.TO_MANY_ERASURE:
                    # 说明少于 k个块满足 kzg_commitment，那么说明这个 kzg_commitment不被承认
                    log.write_log("ERROR", "Slot {} Replicate Chunk KZG proof Verify Failed...".format(replicate_package.slot_hash, replicate_package.row_index))
                else:
                    # log.write_log("DEBUG", "Slot {} Replicate Chunk {} KZG Proof Verify Success...".format(replicate_package.slot_hash, replicate_package.row_index))
                    # KZG验证通过，那么按照 index将 ec还原
                    decoder = ReedSolomonDecoder()
                    recover_data , err = decoder.decode(encoded_chunks=ec_chunks)
                    if err != ErasureCodeRecoverError.NONE:
                        log.write_log("ERROR", "Slot {} Replicate Chunk {} cannot recover...".format(replicate_package.slot_hash, replicate_package.row_index))
                    else:
                        # 可以恢复，那么验证 merkle
                        merkle_proof: MerkleProof = replicate_package.merkle_proof
                        if not merkle_proof.verify(recover_data, hf=HashFunction.SHA256):
                            log.write_log("ERROR", "Slot {} Replicate Chunk {} Merkle Proof Verify Failed...".format(replicate_package.slot_hash, replicate_package.row_index))
                        else:
                            # 通过检测，可以留下对应的存储块
                            chunk_to_store: ReplicateChunk = chunks[replicate_package.store_col_index]
                            self.process_chunk_to_store(sign=replicate_package.sign, slot=replicate_package.slot, slot_hash=replicate_package.slot_hash, row_index=replicate_package.row_index, chunk_to_store=chunk_to_store)
                # chunk_to_store: ReplicateChunk = self.channel.to_receiver_chunk_store_channel.get(timeout=0.01) # 取出grpc带来的复制块
                #             self.process_chunk_to_store(chunk_to_store=chunk_to_store) # 开始存储 todo 这里可以多开几个线程并行
                            log.write_log("STORAGE", "Receive slot {} chunk {}, commitment verify Success, finish store in local...".format(replicate_package.slot_hash, replicate_package.row_index))
            except Exception as e:
                raise RuntimeError(e)
    def process_chunks_to_load_test(self):
        while True:
            if self.channel.test_collect_pass_receiver_channel.empty():
                continue
            try:
                item = self.channel.test_collect_pass_receiver_channel.get(timeout=0.01)
                slot, output, nb_row = item[0], item[1], item[2]
                local_chunks = []
                for row_index in range(nb_row):
                    chunk_to_load: ErasureCodeChunk = self.process_chunk_to_load(slot_hash=slot.hash, row_index=row_index)
                    local_chunks.append(chunk_to_load)
                self.channel.test_collect_pass_grpc_channel.put((slot, output, local_chunks)) # 传递给grpc
            except Exception as e:
                raise RuntimeError(e)
    # def process_chunks_to_load(self):
    #     while True:
    #         if self.channel.collect_pass_receiver_channel.empty():
    #             continue
    #         try:
    #             item = self.channel.collect_pass_receiver_channel.get(timeout=0.01)
    #             slot_hashs, mission = item[0], item[1]
    #             print(slot_hashs, mission)
    #             # connect = self.channel.get_connect_channel(mission)
    #             result = []
    #             for slot_hash in slot_hashs:
    #                 ec_chunks = self.process_chunk_to_load_without_row_index(slot_hash)
    #                 result.extend(ec_chunks)
    #             self.channel.collect_connect_channel.put(result) # 传递给grpc
    #         except Exception as e:
    #             raise RuntimeError(e)
    def start(self):
        processes = [
            # Process(target=self.process_chunks_to_load),
            Process(target=self.process_chunks_to_load_test),
            Process(target=self.process_chunks_to_store)
        ]
        for process in processes:
            process.start()
        for process in processes:
            process.join()