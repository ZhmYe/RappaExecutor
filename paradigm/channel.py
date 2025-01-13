from multiprocessing import Queue, Manager

from paradigm.replicate import ReplicateChunk, ChunkReplicateRecord, ReplicatePackage
from paradigm.slot import CommitSlotItem
from network.Grpc.service.service_pb2 import RecoverSlotChunk


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

        # self.collect_pass_receiver_channel = manager.Queue()
        # self.collect_pass_grpc_channel = manager.Queue()

        self.collect_connect_channel = manager.Queue()
    def update_store_chunk(self, slot_hash, new_store_chunk_item, row_index):
        if not self.store_chunks.get(slot_hash):
            self.store_chunks[slot_hash] = self.manager.dict()
        self.store_chunks[slot_hash][row_index] = new_store_chunk_item
    # def create_connect_channel(self, mission):
    #     self.collect_connect_channel[mission] = self.manager.Queue()
    #     return self.collect_connect_channel[mission]
    # def get_connect_channel(self, mission):
    #     if not self.collect_connect_channel[mission]:
    #         raise RuntimeError("not such connection!!!")
    #     return self.collect_connect_channel[mission]
    # def delete_connect_channel(self, mission):
    #     del self.collect_connect_channel[mission]
    def load_store_chunk(self, slot_hash):
        # 这里用于在grpc处得到收集的chunk
        chunks = []
        if not self.store_chunks.get(slot_hash):
            return []
        for row_index, chunk in self.store_chunks[slot_hash].items():
            chunks.append(RecoverSlotChunk(
                hash=chunk.slot_hash,
                row=chunk.row_index,
                col=chunk.col_index,
                chunk=chunk.load()
            ))
        return chunks
    def update_slot_buff(self):
        pass