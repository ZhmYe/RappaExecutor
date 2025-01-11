"""
    NOTE: SimpleReceiver
    Receiver的主要功能是，收集来自节点（包括自己）的数据块，按照既定规则存在本地，并记录相关索引
"""
import os
from multiprocessing import Process, Queue

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

class MockerReceiver:
    def __init__(self, channel: Queue):
        self.storage_path = os.path.join(get_project_root(), BHExecutionNodeGlobalConfig.STORAGE_PATH) # 存储冗余数据块的路径
        # log.write_log("DEBUG", "Init Storage Receiver from config, storage_path: {}".format(self.storage_path))
        self.store_chunks: dict = {} # 存储 chunk，通过 slot_hash作为 key
        # self.store_chunk_channel = store_chunk_channel # 通过这一通道传递要存储的 slot
        self.channel = channel


    def process_chunk_to_store(self, sign, slot, slot_hash, row_index, chunk_to_store: ReplicateChunk):
        # ec_chunk里index代表索引，chunk是具体的 bytes
        # 索引可以不记录在文件里，就单纯的记录在这里Receiver里，一旦节点崩溃，重启以后可以通过向 Master询问自己是第几个 # TODO @YZM 这个要在 master里加上
        # 得到 replicateChunk以后，验证它的 merkle proof和 kzg_proofs
        new_store_chunk_item = StoredChunk(storage_path=self.storage_path, sign=sign, slot=slot, slot_hash=slot_hash, row_index=row_index, chunk_to_store=chunk_to_store)
        data_bytes = chunk_to_store.bytes() # 这里表示纠删码的冗余数据块，bytes直接落盘
        new_store_chunk_item.store(data_bytes) # 存储纠删码
        if not self.store_chunks.get(slot_hash):
            self.store_chunks[slot_hash] = {}
        self.store_chunks[slot_hash][row_index] = new_store_chunk_item
    def process_chunk_to_load(self, slot_hash, row_index)->ErasureCodeChunk:
        # 读取根据 slot_hash来读取
        if not self.store_chunks.get(slot_hash):
            raise ValueError("{} Chunk does not store in this node!!!".format(slot_hash))
        slot_chunks: dict = self.store_chunks[slot_hash]
        if not slot_chunks.get(row_index):
            print(self.store_chunks)
            raise ValueError("{} Chunk does not store {} chunk in this node!!!".format(slot_hash, row_index))
        store_chunk_item: StoredChunk = self.store_chunks[slot_hash][row_index]
        chunk = store_chunk_item.load()
        ec_chunk = ErasureCodeChunk(chunk, store_chunk_item.col_index)
        return ec_chunk
    def start(self):
        while True:
            # Get a task from the task pool (blocking)
            if self.channel.empty():
                continue
            try:
                replicate_package: ReplicatePackage = self.channel.get(timeout=0.01)
                # 首先验证 package的各个 commitment
                chunks = replicate_package.chunks
                kzg_commitment = replicate_package.kzg_commitment
                ec_chunks: ErasureCodeChunks = ErasureCodeChunks()
                # 验证每个 chunk的 kzg
                for replicate_chunk in chunks:
                    # kzg_proof: KZGProof = replicate_chunk.kzg_proof
                    # if kzg_proof.verify(replicate_chunk.bytes()) and kzg_proof.commitment == kzg_commitment:
                    ec_chunks.add_chunk(ErasureCodeChunk(chunk=replicate_chunk.chunk, index=replicate_chunk.col_index))
                if ec_chunks.check() == ErasureCodeRecoverError.TO_MANY_ERASURE:
                    # 说明少于 k个块满足 kzg_commitment，那么说明这个 kzg_commitment不被承认
                    log.write_log("ERROR", "Slot {} Replicate Chunk KZG proof Verify Failed...".format(replicate_package.slot_hash, replicate_package.row_index))
                else:
                    # TODO @YZM 这里不知道为什么，一旦并发，就会出现decoder 里面json.load失败，输入是一样的，但SimReceiver第一次load可以成功，后面几个MockerReceiver会失败
                    # log.write_log("DEBUG", "Slot {} Replicate Chunk {} KZG Proof Verify Success...".format(replicate_package.slot_hash, replicate_package.row_index))
                    # KZG验证通过，那么按照 index将 ec还原
                    # decoder = ReedSolomonDecoder()
                    # recover_data , err = decoder.decode(encoded_chunks=ec_chunks)
                    # if err != ErasureCodeRecoverError.NONE:
                    #     log.write_log("ERROR", "Slot {} Replicate Chunk {} cannot recover...".format(replicate_package.slot_hash, replicate_package.row_index))
                    # else:
                    #     # 可以恢复，那么验证 merkle
                    #     merkle_proof: MerkleProof = replicate_package.merkle_proof
                    #     if not merkle_proof.verify(recover_data, hf=HashFunction.SHA256):
                    #         log.write_log("ERROR", "Slot {} Replicate Chunk {} Merkle Proof Verify Failed...".format(replicate_package.slot_hash, replicate_package.row_index))
                    #     else:
                    chunk_to_store: ReplicateChunk = chunks[replicate_package.store_col_index]
                    self.process_chunk_to_store(sign=replicate_package.sign, slot=replicate_package.slot, slot_hash=replicate_package.slot_hash, row_index=replicate_package.row_index, chunk_to_store=chunk_to_store)


                    # log.write_log("DEBUG", "Receive slot {} chunk {}, commitment verify Success, finish store in local...".format(replicate_package.slot_hash, replicate_package.row_index))


                # chunk_to_store: ReplicateChunk = self.channel.get(timeout=0.01) # 取出grpc带来的复制块
                # self.process_chunk_to_store(chunk_to_store=chunk_to_store) # 开始存储 todo 这里可以多开几个线程并行

            except Exception as e:
                raise RuntimeError(e)