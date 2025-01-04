"""
    NOTE: SimpleReceiver
    Receiver的主要功能是，收集来自节点（包括自己）的数据块，按照既定规则存在本地，并记录相关索引
"""
import os
from multiprocessing import Process, Queue

from config.config import BHExecutionNodeGlobalConfig
from paradigm.channel import Channel
from paradigm.storage import StoredChunk, ErasureCodeChunk, ReplicateChunk
from utils.function.func import get_project_root
from logger.logger import logWriter as log

class MockerReceiver:
    def __init__(self, channel: Queue):
        self.storage_path = os.path.join(get_project_root(), BHExecutionNodeGlobalConfig.STORAGE_PATH) # 存储冗余数据块的路径
        log.write_log("INFO", "Init Storage Receiver from config, storage_path: {}".format(self.storage_path))
        self.store_chunks: dict = {} # 存储 chunk，通过 slot_hash作为 key
        # self.store_chunk_channel = store_chunk_channel # 通过这一通道传递要存储的 slot
        self.channel = channel


    def process_chunk_to_store(self, chunk_to_store: ReplicateChunk):
        # ec_chunk里index代表索引，chunk是具体的 bytes
        # 索引可以不记录在文件里，就单纯的记录在这里Receiver里，一旦节点崩溃，重启以后可以通过向 Master询问自己是第几个 # TODO @YZM 这个要在 master里加上
        new_store_chunk_item = StoredChunk(storage_path=self.storage_path, chunk_to_store=chunk_to_store)
        data_bytes = chunk_to_store.bytes() # 这里表示纠删码的冗余数据块，bytes直接落盘
        new_store_chunk_item.store(data_bytes) # 存储纠删码
        if not self.store_chunks.get(chunk_to_store.slot_hash):
            self.store_chunks[chunk_to_store.slot_hash] = {}
        self.store_chunks[chunk_to_store.slot_hash][chunk_to_store.row_index] = new_store_chunk_item
    def process_chunk_to_load(self, slot_hash, row_index)->ErasureCodeChunk:
        # 读取根据 slot_hash来读取
        if not self.store_chunks.get(slot_hash):
            raise ValueError("{} Chunk does not store in this node!!!".format(slot_hash))
        slot_chunks: dict = self.store_chunks[slot_hash]
        if not slot_chunks.get(row_index):
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
                chunk_to_store: ReplicateChunk = self.channel.get(timeout=0.01) # 取出grpc带来的复制块
                self.process_chunk_to_store(chunk_to_store=chunk_to_store) # 开始存储 todo 这里可以多开几个线程并行

            except Exception as e:
                raise RuntimeError(e)