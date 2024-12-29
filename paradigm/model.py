# Hints: zhmye
# 这里我们将所有的模型统一用这个格式来写，这样外面统一调用这些方法不会出问题
# ModelInstance
# 1. generate_input: 这个函数目前我在ctgan里就是获取params里的输入
# 2. generate_output: 输出output_size大小的数据，这里的params是有用的，以ctgan为例，它需要一些条件列和条件向量，
#  如果没有，那么会将data_sampler里的原始数据中抽取随机向量，这里的params就作为每个不同模型生成输出要的一些参数
# 3. name 这个目前就是为了格式化输出
# 4. load_model_from_pth_file_path 这个函数就是为了加载模型
# dir_path是模型文件保存的文件夹, model_name是模型的格式化文件名比如{}.pth params是用来给不同模型的特殊文件名的
# 比如ctgan需要sampler
from abc import abstractmethod
from enum import Enum, auto

from model.format import ModelFormatOutput

class ModelEnum(Enum):
    CTGAN = auto()


class ModelInstance:
    @abstractmethod
    def generate_input(self, params=None):
        pass
    @abstractmethod
    def generate_output(self, output_size, params=None) -> ModelFormatOutput:
        pass
    @abstractmethod
    def name(self):
        return "Default_Model_Instance"
    @abstractmethod
    def load_model_from_pth_file_path(self, params:dict):
        pass

class CommitSlotModelParams:
    def __init__(self, name, condition_params: dict):
        self.name = name
        self.condition_params: dict = condition_params