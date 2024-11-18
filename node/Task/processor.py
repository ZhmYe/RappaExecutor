from model.loader import ModelLoader
from .slot import Slot
from utils.function.func import get_model_root
from model.format import ModelInstance, ModelFormatOutput
from logger.logger import logWriter as log
from ..format import SlotItem


# Processor具体处理slot的实例
# 一般我们默认一个task的model是不变的，但是为了完整还是提供了update的接口
class Processor:
    def __init__(self, params: SlotItem):
        # 这里是第一次初始化，根据params里的model加载出模型
        self.model_name = params.get_model_name()
        model_path = get_model_root()
        log.write_log("INFO", "Init Processor with model {} from {}".format(self.model_name, model_path))
        self.loader = ModelLoader(model_path)
        self.instance = self.update_model_instance(self.model_name)


    def process(self, slot: Slot)->ModelFormatOutput:

        output = self.instance.generate_output(slot.size, slot.params)
        log.write_log("TRACK", "Generate output with model {}, sample size: {}, output size: {}".format(self.model_name, slot.size, len(output.output)))
        return output







    def update_model_instance(self, model)->ModelInstance:
        self.model_name = model
        return self.loader.load(model)
