
class Task:
    def __init__(self, sign):
        self.sign = sign
        self.slots = [] # 这里记录每个slot
        # self.finish = False # 这里不存在是否已经完成的情况
        # self.slot_index = -1 # 标记目前处理到哪些slot了，可能没什么用，因为可能Layer2Node的逻辑是等大家一个slot全做完了才会分发任务，因此每次只会有一个slot
        # self.processor = self.init_processor(params=params.slot) # 具体处理slot的实例，包含当前任务使用什么模型等
    def update_slot(self, slot_index):
        self.slots.append(slot_index) # 这里的slot_index是由slotManager返回回来的（当前节点接收到的第几个slot）