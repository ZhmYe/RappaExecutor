# 这里定义一个合成任务
# Hints: zhmye
# 可以修改，目前的想法如下
# 1. 每个合成任务代表着平台向我们后端发来的一次合成数据任务，给它一个标记(sign)
# 2. 每个合成任务会被分成若干个slot，每个参与的节点在每个slot里会被分配到一些小任务
# 3. 为了方便上链，一些元数据会被带着params里传过来，比如开始时间，用户id等等，这些要不要放在这里待定；反正params一定有一个sign
from model.format import ModelFormatOutput
from .slot import Slot
from .processor import Processor
from ..format import PendingTaskPoolItem, SlotItem


class Task:
    def __init__(self, params: PendingTaskPoolItem):
        self.sign = params.sign
        self.slots = [] # 这里记录每个slot
        self.finish = False # 标记任务是否已经完成
        self.slot_index = -1 # 标记目前处理到哪些slot了，可能没什么用，因为可能Layer2Node的逻辑是等大家一个slot全做完了才会分发任务，因此每次只会有一个slot
        self.processor = self.init_processor(params=params.slot) # 具体处理slot的实例，包含当前任务使用什么模型等
    def init_processor(self, params: SlotItem)->Processor:
         return Processor(params) # todo
        # self.processor = None
    def update_slot(self, params:SlotItem):
        # params: todo 这里就是slot需要的params,可以修改成在这里进行处理后再传入
        slot = Slot(params)
        output = self.process_slot(slot)
        self.slots.append(slot)
        return output
    def process_slot(self, slot: Slot)->ModelFormatOutput:
        # 进行某个slot的运行
        return self.processor.process(slot)

    def serialize(self):
        # 为了方便checkpoint或者其它一些需求，这里提供对task的序列化方式，比如json(dict)
        return {
            "sign": self.sign,
            "slots": [slot.serialize for slot in self.slots],
            "is_finish": self.finish,
            # todo
        }
    


    def is_finish(self)->bool:
            return self.finish
    def sign_finish(self):
        self.finish = True
    