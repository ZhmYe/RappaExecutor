from multiprocessing import Queue, Manager

from paradigm.replicate import ReplicateChunk, ChunkReplicateRecord, ReplicatePackage
from paradigm.slot import CommitSlotItem


class Channel:
    def __init__(self, manager: Manager):
        self.manager = manager
        self.to_slot_manager_channel: Queue[CommitSlotItem] = manager.Queue()
        self.to_task_tracker_channel: Queue[CommitSlotItem] = manager.Queue()
        self.to_grpc_replicate_channel: Queue = manager.Queue()
        self.to_grpc_slot_channel: Queue[CommitSlotItem] = manager.Queue()
        self.to_processor_slot_channel: Queue[CommitSlotItem] = manager.Queue()
        self.to_storager_slot_channel: Queue = manager.Queue()
        self.to_receiver_chunk_store_channel: Queue[ReplicatePackage] = manager.Queue()
        self.to_receiver_chunk_load_channel: Queue = manager.Queue()
        self.to_worker_slot_channel: Queue[CommitSlotItem] = manager.Queue()
        self.to_storager_record_channel: Queue = manager.Queue()

        self.slot_buffer_share_dict = manager.dict()
        self.store_chunks = manager.dict()

        self.test_collect_output_channel = manager.Queue()
        self.test_collect_signal_channel = manager.Queue()
        self.test_collect_pass_receiver_channel = manager.Queue()
        self.test_collect_pass_grpc_channel = manager.Queue()
        self.test_replicate_mocker_executor_channel = manager.Queue()
    def update_store_chunk(self, slot_hash, new_store_chunk_item, row_index):
        if not self.store_chunks.get(slot_hash):
            self.store_chunks[slot_hash] = self.manager.dict()
        self.store_chunks[slot_hash][row_index] = new_store_chunk_item
    def update_slot_buff(self):
        pass