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
import os
from abc import abstractmethod
from enum import Enum, auto

from utils.function.path_utils import get_project_root


class ModelEnum(Enum):
    CTGAN = auto() # 测试用的ctgan模型
    BAED  = auto() # 生成图数据的模型
    FINKAN = auto() # 生成表格数据的模型
    ABM = auto() # 生成时序数据的模型

class ModelArgs:
    def __init__(self, model_root, dataset, model_path, args_path, checkpoint_path, is_cuda=False):
        self.model_root = model_root
        self.dataset = dataset
        self.model_path = model_path
        self.args_path = args_path
        self.checkpoint_path = checkpoint_path
        self.is_cuda = is_cuda


class LoadModelParams:
    def __init__(self, model: ModelEnum, checkpoint=None, dataset=None, ):
        if checkpoint is None:
            checkpoint = load_default_checkpoint(model=model)
        if dataset is None:
            dataset = load_default_dataset(model=model)
        self.checkpoint = checkpoint
        self.dataset = dataset
        self.model_path_args: ModelArgs = load_model_args(model=model, dataset=dataset, checkpoint=checkpoint)



def load_default_checkpoint(model: ModelEnum):
    if model == ModelEnum.BAED:
        return 49
    if model == ModelEnum.CTGAN:
        return -1


def load_default_dataset(model: ModelEnum):
    if model == ModelEnum.BAED:
        return "elliptic"
    if model == ModelEnum.CTGAN:
        return "test"
    if model == ModelEnum.FINKAN:
        return "default of credit card clients"
    if model == ModelEnum.ABM:
        return "SHL2_TAQ_600519_202401-202402_defreq"

def load_model_args(model: ModelEnum, dataset=None, checkpoint=None, is_cuda=False) -> ModelArgs:
    project_root = get_project_root()
    if dataset is None:
        dataset = load_default_dataset(model)
    if checkpoint is None:
        checkpoint = load_default_checkpoint(model)
    if model == ModelEnum.BAED:
        # 参考BAED/evaluate.py
        # TODO @YZM 这里需要有个check,判断checkpoint和dataset是否符合要求
        model_root = os.path.join(project_root, "model/BAED")
        model_path = os.path.join(model_root, "wandb/{}/multinomial_diffusion/multistep/{}".format(dataset, "2024-12-26_11-48-15")) # todo
        path_args = "{}/args.pickle".format(model_path)
        path_check = "{}/check/checkpoint_{}.pt".format(model_path, checkpoint)
        return ModelArgs(model_root, dataset, model_path, path_args, path_check, is_cuda=is_cuda)
    if model == ModelEnum.CTGAN:
        model_root = os.path.join(project_root, "model/CTGAN")
        model_path = os.path.join(model_root, "test")
        path_args = None
        path_check = "{}/ctgan_model.pth".format(model_path)
        return ModelArgs(model_root,dataset, model_path, path_args, path_check, is_cuda=is_cuda)
    if model == ModelEnum.FINKAN:
        model_root = os.path.join(project_root, "model/FINKAN")
        model_path = os.path.join(model_root, "model/")
        path_args = os.path.join(model_root, "data")
        # path_check = "{}/synthesizer_model.pth".format(model_path)
        path_check = "{}/test.pth".format(model_path)
        return ModelArgs(model_root, dataset, model_path, path_args, path_check, is_cuda=is_cuda)
    if model == ModelEnum.ABM:
        model_root = os.path.join(project_root, "model/ABM_")
        model_path = os.path.join(model_root, "model/")
        path_args = os.path.join(model_root, "data")
        path_check = "{}/model_params.tsf".format(model_path)
        return ModelArgs(model_root, dataset, model_path, path_args, path_check, is_cuda=is_cuda)






# 这里统一规定模型的输出 # todo 不断完善
# 要考虑的是，我们将合成任务分成了若干次，然后事实上每个小任务在模型处可能会因为batch_size变成几批，每一批对应一个Input，output
# 所以最后的结果可能是(input, output)对，能否直接合并成(inputs, outputs)这样两个向量?
class ModelFormatOutput:
    def __init__(self, model_name, _input, output, params: dict):
        self.name = model_name
        self.input = _input
        self.output = output
        self.params = params
    def format_json(self) -> dict:
        return {
            "model": self.name,
            "input": self.input,
            "output": self.output,
            "params": self.params
        }



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