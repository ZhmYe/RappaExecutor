"""
    NOTE: SlotManager管理节点收到的所有CommitSlotItem，并为他们赋予一个独特的index
"""
from network.Grpc.grpc_engine import GrpcEngine
from paradigm.channel import Channel
from paradigm.slot import SlotState

from paradigm.slot import CommitSlotItem
from processor.processor import  Processor
from logger.logger import logWriter as log

class SlotManager:
    def __init__(self, channel: Channel):
        self.slots = [] # 所有的CommitSlotItem,追踪他们的状态
        # self.processor: Processor = None # processor会处理所有的unprocessed的slot
        # self.grpc_engine: GrpcEngine = None # grpc_engine用于处理undetermined的slot，发起commitSlot请求给master
        self.channel = channel
        # self.slot_channel = slot_channel # 所有的后续的slot都传递到这里

        # 这里是所有连接的通道
        # self.to_slot_manager_channel: Queue[CommitSlotItem] = to_slot_manager_channel # 其它进程传递给slotManager的
        # self.to_task_tracker_channel: Queue[CommitSlotItem] = None # 给taskTracker新的slot


    # def set_to_task_tracker_channel(self, to_task_tracker_channel: Queue[CommitSlotItem]):
    #     self.to_task_tracker_channel = to_task_tracker_channel
    #
    # def check_channel_connect(self)->True:
    #     if self.to_slot_manager_channel is None:
    #         return False
    #     if self.to_task_tracker_channel is None:
    #         return False



    # def set_grpc_engine(self, grpc_engine: GrpcEngine):
    #     self.grpc_engine = grpc_engine
    # def set_processor(self, processor: Processor):
    #     self.processor = processor

    def handle_new_receive_slot(self, slot: CommitSlotItem) -> int:
        # 这里针对最新的unprocessed的slot
        if slot.state != SlotState.UNPROCESSED:
            raise ValueError("SlotManager.handle_receive_slot should process Unprocessed Slot!!!")
        index = len(self.slots)
        slot.set_index(index)
        self.slots.append(slot) # 添加全新的slot
        # 将这个slot放到channel中
        # self.slot_channel.put(slot)  # 这里暂时就认为channel把整个slot都放进去了，后续看看有没有更好的实现方法
        # print(len(self.slots))
        return index
    def process(self):
        # 处理channel中的slot
        while True:
            if self.channel.to_slot_manager_channel.empty():
                continue
            try:
                slot: CommitSlotItem = self.channel.to_slot_manager_channel.get(timeout=1)  # Wait for a task
                # 说明是新的slot
                if slot.index == -1:
                    self.handle_new_receive_slot(slot)
                # todo 判断异常invalid
                if slot.is_unprocess():
                    # 如果是新的slot，那么交给process处理
                    log.write_log("EXECUTION", "Receive Unprocessed Slot, Sign: {}, Slot: {}".format(slot.sign, slot.slot))
                    self.channel.to_processor_slot_channel.put(slot) # 传递给processor
                    # self.processor.process_unprocessed_slot(slot)
                if slot.is_undetermined():
                    # 这里说明slot已经生成了输出并且分发了冗余块，等待上传commitment，转发给grpc_engine
                    # todo 判断是否赋予了commitment
                    # todo 这里暂时先这样写
                    # if not slot.has_been_commit(): # 如果has_been_commit 那么是grpc返回回来用来更新的
                    log.write_log("EXECUTION", "Receive Undetermined Slot, Sign: {}, Slot: {}".format(slot.sign, slot.slot))
                    self.channel.to_grpc_slot_channel.put(slot) # 传递给grpc_engine
                        # self.grpc_engine.process_undetermined_slot(slot)
                    # else:
                    #     log.write_log("EXECUTION", "Update Undetermined Slot, Sign: {}, Slot: {}, Hash: {}".format(slot.sign, slot.slot, slot.hash))

                if slot.is_justified():
                    # 这里说明slot已经通过投票， 这里暂时考虑为通过投票后才需要进行zkp生成，不然浪费资源 todo
                    # 首先判断是否需要可信证明
                    log.write_log("EXECUTION", "Update Justified Slot, Sign: {}, Slot: {}, Hash: {}".format(slot.sign, slot.slot, slot.hash))
                    if slot.check_is_reliable():
                        # 不需要，那么无需额外逻辑 todo
                        pass
                    else:
                        # 传递给生成可信证明的dataProver todo @YZM
                        pass # 还没实现，暂时就先pass todo
                if slot.is_finalized():
                    # slot已经finalize,暂时没有额外逻辑
                    log.write_log("EXECUTION", "Update Finalized Slot, Sign: {}, Slot: {}, Hash: {}".format(slot.sign, slot.slot, slot.hash))
                    pass


                # 更新slot状态
                self.slots[slot.index] = slot

            except Exception as e:
                raise RuntimeError(e)
    def start(self):
        # thread = threading.Thread(target=self.process)
        # thread.start()
        self.process()