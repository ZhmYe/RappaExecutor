from typing import List
from enum import Enum, auto


class ReplicateChunk:
    def __init__(self, sign, slot, row_index, col_index, slot_hash, chunk):
        self.sign = sign
        self.slot = slot
        self.row_index = row_index
        self.col_index = col_index
        self.slot_hash = slot_hash
        self.chunk = chunk
    def bytes(self):
        return self.chunk # todo 这里等待实现

class ReplicateState(Enum):
    SUCCESS = auto()
    FAILED = auto()
    # TODO

# 这里记录一个由当前节点生成的数据被分发的记录，便于回收并恢复
# 需要记录的是: 1. 每个chunk被发给了谁; 2. padding_size
# 其它的数据全部放到CommitSlot里去
class ChunkReplicateRecord:
    # chunk_replicate_list: List[str]是ip的列表，对应index的chunk被发到对应的ip
    def __init__(self,  slot_hash, index, nb_chunk, padding_size=0):
        self.slot_hash = slot_hash
        self.replicates = ["" for i in range(nb_chunk)]
        self.padding_size = padding_size
        self.index = index
    def check(self):
        if any([ip == "" for ip in self.replicates]):
            return ReplicateState.FAILED
        return ReplicateState.SUCCESS
    def record_success_replicate(self, index, ip):
        #todo 这里要check
        self.replicates[index] = ip
