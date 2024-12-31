# TaskTracker 用于管理一个节点要处理的所有任务
# 更新某个任务(以sign标识)在本地的完成情况（只要接收到了就存下来）
"""
    NOTE: 这里的TaskTracker和Master的TaskManager不同，严格意义上不需要维护slot的track，因为可能节点不会参与所有的slot
"""
from paradigm.slot import CommitSlotItem
from paradigm.task import Task
from queue import Queue
import threading
from logger.logger import logWriter as log
from task.SlotManager import SlotManager


class TaskTracker:
    def __init__(self, pending_task_pool: Queue = Queue()):
        self.tasks = [] # 所有的任务，任务类型为Task
        self.tasks_map = {} # 任务映射， 由sign映射到self.tasks的Index上
        self.slot_manager:SlotManager = None
        self.pending_task_pool = pending_task_pool
    def set_slot_manager(self, slot_manager: SlotManager):
        self.slot_manager = slot_manager
    """
        NOTE: handle_receive_slot 接收到新的slot后调用
        1. 首先根据sign来判断是否曾经收到过这一任务，得到或新建相应任务
        2. 将slot传递给slot_manager
    """
    def handle_receive_slot(self, slot: CommitSlotItem):
        if slot.sign is None:
            raise ValueError("TaskPoolItem.sign should not be None")
            # 取出对应的task，这样写可能不太好，先这样
            # 考虑到会有并发的请求，所以会出现上一个任务还没做完下一个任务就开始了
            # 这里先不考虑并发运行task todo
        if slot.sign not in self.tasks_map:
            self.tasks_map[slot.sign] = len(self.tasks)
            task = Task(slot.sign) # 只需要一个sign即可
            self.tasks.append(task)
            log.write_log("EXECUTION", "Receive New Task, Sign: {}, Slot: {}".format(slot.sign, slot.slot))
        else:
            task = self.tasks[self.tasks_map[slot.sign]]
        slot_index = self.slot_manager.handle_receive_slot(slot) # 向slotManager传递slot
        task.update_slot(slot_index) # 更新
    def process(self):
        while True:
            if self.pending_task_pool.empty():
                continue
            try:
                task_slot: CommitSlotItem = self.pending_task_pool.get(timeout=1)
                self.handle_receive_slot(task_slot)
            except Exception as e:
                raise RuntimeError(e)
    def start(self):
        # 启动所有客户端监视线程
        thread = threading.Thread(target=self.process)
        thread.start()