# Grpc或者http解析完来自Layer2Node的任务，将其解析为如下内容

# Version 1.0
# id: 节点标识，没什么太多的用
# task: task的唯一标识也就是task.sign
# 以下为slotItem内容
    # slot: task的slot，用于说明是哪一个阶段
    # size: 生成数据量
    # model: dict
    # model.name: 模型
    # model.params: 模型的一些相关参数
# 其实model.name应该是不会变的，先这样放着todo




class SlotItem:
    def __init__(self, slot_id, size, model_name, model_params):
        self.id = slot_id
        self.size = size
        self.model = {
            "name": model_name,
            "params": model_params
        }
    def get_model_name(self):
        return self.model["name"]
    def get_model_params(self):
        return self.model["params"]
    def format(self):
        return {
            "slot_id": self.id,
            "data_size": self.size,
            "model": self.model
        }
class TaskPoolItem:
    def __init__(self, tid, sign, slot, size, model_name, model_params: dict=None):
        self.id = tid
        self.sign = sign
        self.slot = SlotItem(slot, size, model_name, model_params)
    def model(self):
        return self.slot.get_model_name()
    def params(self):
        return self.slot.get_model_params()
    def format(self):
        return {
            "id": self.id,
            "sign": self.sign,
            "slot": self.slot.format()
        }