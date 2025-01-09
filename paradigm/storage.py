import os
from enum import Enum,auto
from typing import List

from config.config import BHExecutionNodeGlobalConfig
from paradigm.mod import ModelOutputType
from paradigm.replicate import ReplicateChunk
from utils.cryptography.commitment.commitment_computer import CommitmentComputer, CommitmentType
from utils.cryptography.commitment.kzg.kzg_commitment import KZGCommitment

"""
    NOTE: 这里是关于存储的部分
"""




# 表示一个将被存储的文件块
# 需要记录的是: 1. 是哪个任务的第几个slot; 2. 是第几个chunk; 3. 存储的路径是什么
class StoredChunk:
    def __init__(self, storage_path, sign, slot, slot_hash, row_index, chunk_to_store: ReplicateChunk):
        # self.node_id = node_id #这个不重要
        self.sign = sign
        self.slot = slot
        self.row_index = row_index
        self.col_index = chunk_to_store.col_index
        self.slot_hash = slot_hash # Master为每个 CommitSlotItem赋予了slot_hash，这里记录，方便作为索引
        self.store_path = self.generate_file_store_path(storage_path)
    def generate_file_store_path(self, storage_path):
        # 构建分级存储路径
        file_dir = os.path.join(storage_path, str(self.sign), str(self.slot))
        file_path = os.path.join(file_dir, "{}-row-{}-{}-chunk.slot".format(self.slot_hash, self.row_index, self.col_index))

        # 确保存储路径存在
        os.makedirs(file_dir, exist_ok=True)
        return file_path
    def store(self, data_bytes):
        # 写入文件
        try:
            with open(self.store_path, "wb") as f:
                # json.dump(chunk_data, f, ensure_ascii=False, indent=4)
                f.write(data_bytes) # 直接写
                f.close()
        except Exception as e:
            raise IOError(f"Failed to store chunk locally at { self.store_path }: {e}")
        # 这里直接存储
        pass
    def load(self):
        # 这里读取
        # 写入文件
        try:
            with open(self.store_path, "rb") as f:
                # json.dump(chunk_data, f, ensure_ascii=False, indent=4)
                data = f.read()
                f.close()
                return data
        except Exception as e:
            raise IOError(f"Failed to store chunk locally at { self.store_path }: {e}")
        # 这里直接存储


    # def set_slot_hash(self, slot_hash):


"""
    NOTE: 这里是关于纠删码的部分
"""
class ErasureCodeRecoverError(Enum):
    INVALID_COMMITMENT = auto()
    NOT_MATCH_COMMITMENT = auto()
    TO_MANY_ERASURE = auto()
    # todo
    NONE = auto()

# ErasureCodeChunk 表示一个ec数据块，需要表示其index
class ErasureCodeChunk:
    def __init__(self, chunk, index):
        self.index = index
        self.chunk = chunk
# ErasureCodeChunks 就是所有的数据块，提供排序功能，并判断是否可恢复（KZG）
class ErasureCodeChunks:
    def __init__(self, padding_size=0, n=BHExecutionNodeGlobalConfig.EC_PARAMS_N, k=BHExecutionNodeGlobalConfig.EC_PARAMS_K, output_type=ModelOutputType.DATAFRAME):
        # TODO 这里需要加入文件类型如dataframe @YZM
        self.n = n
        self.k = k # 这两个参数暂时放在这里，考虑后面是否可以动态调整 todo
        self.padding_size = padding_size
        self.encoded_chunks: List[ErasureCodeChunk] = []
        self.kzg_commitment: KZGCommitment = KZGCommitment()# 这里设置KZG承诺 todo
        self.output_type = output_type
    def add_chunk(self, chunk: ErasureCodeChunk):
        self.encoded_chunks.append(chunk) # 这边就简单的插入即可
    def add_chunks(self, chunks: List[ErasureCodeChunk]):
        for chunk in chunks:
            self.add_chunk(chunk)
    def compute_kzg_commitment(self):
        # TODO 这里计算纠删码的KZG承诺 @YZM
        commitment_computer = CommitmentComputer()
        self.kzg_commitment = commitment_computer.compute_commitment([chunk.chunk for chunk in self.encoded_chunks], commitment_type=CommitmentType.KZG)
    def check(self) -> ErasureCodeRecoverError:
        # 在check之前一定要先去重
        if len(self.encoded_chunks) < self.k:
            return ErasureCodeRecoverError.TO_MANY_ERASURE
        # todo 这里需要check kzg承诺
        return ErasureCodeRecoverError.NONE
    def recover(self, decoder):
        # 将chunks按照index进行排序，并判断是否有重复
        # 使用字典来去重，同时保持插入顺序
        unique_chunks = list({chunk.index: chunk for chunk in self.encoded_chunks}.values())

        # 将去重后的chunks按照index进行排序
        self.encoded_chunks = sorted(unique_chunks, key=lambda x: x.index)
        error = self.check()
        if error != ErasureCodeRecoverError.NONE:
            return [], error
        # 传入decoder用于还原数据
        chunks, indices = zip(*[(item.chunk, item.index) for item in self.encoded_chunks[:self.k]])
        # print(chunks, indices)
        decoded_chunks = decoder.decode(chunks, indices) # decoder必须要实现decode todo 这样写不太严谨
        return decoded_chunks, ErasureCodeRecoverError.NONE