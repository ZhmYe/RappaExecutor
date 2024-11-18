from node.format import SlotItem


class Slot:
    def __init__(self, params: SlotItem):
        #params
            # slot: task的slot，用于说明是哪一个阶段
            # size: 生成数据量
            # model: dict
            # model.name: 模型
            # model.params: 模型的一些相关参数
        self.id = params.id
        self.size = params.size
        self.model = params.get_model_name()
        self.params = params.get_model_params()