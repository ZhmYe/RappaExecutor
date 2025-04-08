import os

from model.ABM.instance import ABM_MODEL_INSTANCE
from model.BAED.instance import BAED_MODEL_INSTANCE
from model.CTGAN.instance import CTGAN_Model_Instance
from model.FINKAN.instance import FINKAN_MODEL_INSTANCE
from utils.function.func import get_model_params_dict
from paradigm.model import ModelEnum, ModelInstance, load_model_args
from logger.logger import logWriter as log


class ModelLoader:
    def __init__(self, path):
        """
        初始化 ModelLoader 实例

        Args:
            path (str): 模型文件所在目录路径。
        """
        self.path = path  # 模型文件路径

    def load_all_model_support(self, is_cuda: bool):
        instances = {}

        # 初始化 tqdm 进度条
        # progress_bar = tqdm([member.name for member in ModelEnum],
        #                     desc="Loading models",  # 初始描述
        #                     bar_format="{l_bar}{bar:30}{r_bar}",  # 美化进度条
        #                     ncols=80)

        for model_enum in [member.name for member in ModelEnum]:
        #     # 根据模型名称设置不同的描述
        #     # progress_bar.set_description(f"Loading {model_enum}")
        #     # tqdm.write(f"Loading model: {model_enum}")
            log.write_log("INFO", "Start Load Model {}, CUDA:{}...".format(model_enum, "true" if is_cuda else "false"))
            # if model_enum == "CTGAN":
            #     continue
        #     # 加载模型
            instance = self.load(model_enum, is_cuda)
            instances[model_enum] = instance
        # TODO 这里先只加载CTGAN
        # model_enum = 'CTGAN'
        # instance = self.load(model_enum)
        # instances[model_enum] = instance
        log.write_log("INFO", "Load All Supported Model Success...")

        return instances

    def load(self, model_type, is_cuda: bool):
        """
        加载指定类型的模型实例。

        Args:
            model_type (str): 模型类型，例如 "CTGAN"。
            model_pth_name (str): 模型文件名，必须以 ".pth" 结尾。

        Returns:
            模型实例（如 CTGAN_Model_Instance）。

        Raises:
            AssertionError: 如果模型类型不受支持或文件名格式错误。
            FileNotFoundError: 如果模型文件不存在。
        """
        # 支持的模型类型
        # config = ["CTGAN"]  # 如果有新模型类型，需要在此处扩展

        # 校验模型类型
        assert model_type in [member.name for member in
                              ModelEnum], f"Unsupported model type: {model_type}. Supported types: {[member.name for member in ModelEnum]}"

        # 校验文件名格式
        # assert model_pth_name.endswith(".pth"), f"Invalid model file name: {model_pth_name}. Only '.pth' files are supported."
        # torch.manual_seed(0)

        # todo 这里需要写的规范一点，放到utils/function/func.py去
        # 根据模型类型加载实例
        if model_type == "CTGAN":
            model_args = load_model_args(model=ModelEnum.CTGAN, is_cuda=is_cuda)
            instance = CTGAN_Model_Instance(model_args=model_args)
            return instance
        if model_type == "BAED":
            model_args = load_model_args(model=ModelEnum.BAED, is_cuda=is_cuda)
            instance = BAED_MODEL_INSTANCE(model_args=model_args)
            return instance
            # 模型文件完整路径
        if model_type == "FINKAN":
            model_args = load_model_args(model=ModelEnum.FINKAN, is_cuda=is_cuda)
            instance = FINKAN_MODEL_INSTANCE(model_args=model_args)
            return instance
        if model_type == "ABM":
            model_args = load_model_args(model=ModelEnum.ABM, is_cuda=is_cuda)
            instance = ABM_MODEL_INSTANCE(model_args=model_args)
            return instance

        else:
            raise ValueError(f"Model type '{model_type}' is not implemented.")  # 理论上不会到这里
