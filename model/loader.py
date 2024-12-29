import os
from model.CTGAN.instance import CTGAN_Model_Instance
from model.format import ModelInstance
from utils.function.func import get_model_params_dict
from paradigm.model import ModelEnum

class ModelLoader:
    def __init__(self, path):
        """
        初始化 ModelLoader 实例

        Args:
            path (str): 模型文件所在目录路径。
        """
        self.path = path  # 模型文件路径
    def load_all_model_support(self):
        # instances = []
        # instance_map = {}
        instances = {}
        for model_enum in [member.name for member in ModelEnum]:
            instance = self.load(model_enum)
            instances[model_enum] = instance
            # instances.append(instance)
        # print(instance_map)
        return instances
    def load(self, model_type) -> ModelInstance:
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
        assert model_type in [member.name for member in ModelEnum], f"Unsupported model type: {model_type}. Supported types: {[member.name for member in ModelEnum]}"

        # 校验文件名格式
        # assert model_pth_name.endswith(".pth"), f"Invalid model file name: {model_pth_name}. Only '.pth' files are supported."

        # 模型文件完整路径
        model_path = os.path.join(self.path, model_type)

        # 检查模型文件是否存在
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file '{model_path}' not found.")
        # todo 这里需要写的规范一点，放到utils/function/func.py去
        # 根据模型类型加载实例
        if model_type == "CTGAN":
            instance = CTGAN_Model_Instance(model_path)
            instance.load_model_from_pth_file_path(get_model_params_dict("CTGAN"))
            return instance

        else:
            raise ValueError(f"Model type '{model_type}' is not implemented.")  # 理论上不会到这里
