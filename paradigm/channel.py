from multiprocessing import Queue, Manager

from paradigm.replicate import ReplicateChunk, ChunkReplicateRecord
from paradigm.slot import CommitSlotItem


class Channel:
    def __init__(self, manager: Manager):
        self.to_slot_manager_channel: Queue[CommitSlotItem] = manager.Queue()
        self.to_task_tracker_channel: Queue[CommitSlotItem] = manager.Queue()
        self.to_grpc_replicate_channel: Queue = manager.Queue()
        self.to_grpc_slot_channel: Queue[CommitSlotItem] = manager.Queue()
        self.to_processor_slot_channel: Queue[CommitSlotItem] = manager.Queue()
        self.to_storager_slot_channel: Queue = manager.Queue()
        self.to_receiver_chunk_store_channel: Queue[ReplicateChunk] = manager.Queue()
        self.to_receiver_chunk_load_channel: Queue = manager.Queue()
        self.to_worker_slot_channel: Queue[CommitSlotItem] = manager.Queue()
        self.to_storager_record_channel: Queue = manager.Queue()

        self.slot_buffer_share_dict = manager.dict()