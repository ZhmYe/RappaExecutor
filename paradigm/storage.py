from enum import Enum,auto
from typing import List

from config.config import BHExecutionNodeGlobalConfig
from paradigm.mod import ModelOutputType

"""
    NOTE: 这里是关于存储的部分
"""




# 表示一个将被存储的文件块
# 需要记录的是: 1. 从哪个节点发过来的; 2. 是哪个任务的第几个slot; 3. 是第几个chunk; 4. 存储的路径是什么
class StoredChunk:
    def __init__(self, node_id, sign, slot, index):
        self.node_id = node_id
        self.sign = sign
        self.slot = slot
        self.index = index
        self.store_path = self.generate_file_store_path()
    def generate_file_store_path(self):
        return ""
    def store(self):
        # 这里直接存储
        pass


# 这里记录一个由当前节点生成的数据被分发的记录，便于回收并恢复
# 需要记录的是: 1. 每个chunk被发给了谁; 2. padding_size
# 其它的数据全部放到CommitSlot里去
class ChunkReplicateRecord:
    # chunk_replicate_list: List[str]是ip的列表，对应index的chunk被发到对应的ip
    def __init__(self, chunk_replicate_list: List[str], padding_size=0):
        self.replicates = chunk_replicate_list
        self.padding_size = padding_size

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
        self.encoded_chunks = []
        self.commitment = "" # 这里设置KZG承诺 todo
        self.output_type = output_type
    def add_chunk(self, chunk: ErasureCodeChunk):
        self.encoded_chunks.append(chunk) # 这边就简单的插入即可
    def add_chunks(self, chunks: List[ErasureCodeChunk]):
        for chunk in chunks:
            self.add_chunk(chunk)
    def compute_commitment(self):
        # TODO 这里计算纠删码的KZG承诺 @YZM
        pass
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