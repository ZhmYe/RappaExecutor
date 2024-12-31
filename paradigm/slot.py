from enum import Enum, auto

from click import UNPROCESSED

from config.config import BHExecutionNodeGlobalConfig
from paradigm.model import CommitSlotModelParams
from paradigm.storage import ChunkReplicateRecord

"""
    NOTE: CommitSlotItem和Master中的CommitSlotItem类似
    用于维护一个slot的完整周期，但在这里比Master里多一个状态
    1. UNPROCESSED
    2. UNDETERMINED
    3. JUSTIFIED
    4. FINALIZED
"""

class SlotState(Enum):
    UNPROCESSED = auto()
    UNDETERMINED = auto()
    JUSTIFIED = auto()
    FINALIZED = auto()
    INVALID = auto()

class InvalidCommitType(Enum):
    INVALID_SLOT = auto()
    EXPIRE_SLOT = auto()
    INVALID_COMMITMENT = auto()
    VERIFIED_FAILED = auto()
    UNKNOWN = auto()
    NONE = auto()



class CommitSlotItem:
    def __init__(self, sign, slot, size, params: CommitSlotModelParams):
        self.index = -1 # 在SlotManager里的id
        self.state: SlotState = SlotState.UNPROCESSED # 初始状态为Unprocessed
        self.invalid_type: InvalidCommitType = InvalidCommitType.UNKNOWN # 异常状态还未知
        self.node_id = BHExecutionNodeGlobalConfig.NODE_ID # 这里要保证已经load了配置
        self.sign = sign # 任务标识
        self.slot = slot # slot位置
        # todo 这里暂时先不写epoch
        self.size = size # 这里的size是分配的总的size
        self.process = 0 # 这里的process是最后完成的process，在状态被设置为Undetermined的时候会更新process
        self.is_reliable = False
        self.params: CommitSlotModelParams = params # 输入模型参数
        self.commitment = "" # todo 这里还有一个commitment
        self.hash = ""
        self.replicate_records: ChunkReplicateRecord = None
    def set_index(self, index):
        self.index = index
    def check_is_reliable(self) -> bool:
        return self.params.is_reliable # todo 这里要求一定要有这个参数
    def is_unprocess(self) -> bool:
        return self.state == SlotState.UNPROCESSED
    def sign_as_processed(self):
        self.state = SlotState.UNDETERMINED
    def is_undetermined(self) -> bool:
        return self.state == SlotState.UNDETERMINED
    def sign_as_justified(self):
        self.state = SlotState.JUSTIFIED
    def is_justified(self) -> bool:
        return self.state == SlotState.JUSTIFIED
    def sign_as_finalized(self):
        self.state = SlotState.FINALIZED
    def is_finalized(self) -> bool:
        return self.state == SlotState.FINALIZED
    def set_commitment(self, commitment):
        self.commitment = commitment
    def has_been_commit(self):
        return self.hash != ""
    def set_hash(self, slot_hash):
        self.hash = slot_hash
    def set_replicate_record(self, record: ChunkReplicateRecord):
        self.replicate_records = record