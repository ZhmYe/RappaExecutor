"""
    NOTE: MockerCollector
    这里模拟要把所有存储的内容收回
    最终的代码中不应该有collector，应该是前后端向Master发起collect，然后Master将collect要的slot_hash通过grpc/heartbeat传递给所有节点，然后节点将自己本地的对应部分发给master
    master将结果拼回
"""
import threading
from typing import List

from paradigm.channel import Channel
from paradigm.slot import CommitSlotItem


class MockerCollector:
    def __init__(self, channel: Channel):
        self.channel = channel
        self.finalized_slots: dict = {} # 这里存slot_hash-> output(dataframe)
    def process_slot_output(self):
        while True:
            if self.channel.test_collect_output_channel.empty():
                continue
            try:
                item = self.channel.test_collect_output_channel.get(timeout=0.01)
                slot, output, nb_chunks = item[0], item[1], item[2]
                self.finalized_slots[slot.hash] = (output, nb_chunks)
            except Exception as e:
                raise RuntimeError(e)
    def process_finalize_signal(self):
        while True:
            if self.channel.test_collect_signal_channel.empty():
                continue
            try:
                slot: CommitSlotItem = self.channel.test_collect_signal_channel.get(timeout=0.01)
                # 说明slot_hash对应的slot已经finalize了，那么可以测试一下collect，将output发过去
                # 这里就不判断不存在了
                output, nb_chunks = self.finalized_slots[slot.hash]
                self.channel.test_collect_pass_receiver_channel.put((slot, output, nb_chunks))
            except Exception as e:
                raise RuntimeError(e)
    def start(self):
        process_finalize = threading.Thread(target=self.process_finalize_signal)
        process_slot = threading.Thread(target=self.process_slot_output)
        process_finalize.start()
        process_slot.start()

