import threading
from multiprocessing import Process, Queue

from mocker.mocker_receiver import MockerReceiver
from network.format import BHExecutionAddress
from paradigm.replicate import ReplicatePackage
from paradigm.storage import ReplicateChunk, ErasureCodeChunk


class MockerExecutor:
    def __init__(self, _id, ip: BHExecutionAddress, channel):
        self.fake_receive_pool = Queue()
        self.receiver = MockerReceiver(channel=self.fake_receive_pool)
        self.id = _id
        self.ip = ip
    def replicate_chunk(self, replicate_chunk: ReplicateChunk):
        self.fake_receive_pool.put(replicate_chunk)
    def replicate_package(self, replicate_package: ReplicatePackage):
        self.fake_receive_pool.put(replicate_package)
    def load(self, slot_hash, row_index)->ErasureCodeChunk:
        return self.receiver.process_chunk_to_load(slot_hash=slot_hash, row_index=row_index)
    def start(self):
        thread = threading.Thread(target=self.receiver.start)
        thread.start()
        # self.receiver.start()