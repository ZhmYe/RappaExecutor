import os.path
import pickle
import time
from abc import ABC, abstractmethod
import torch
from ctgan import CTGAN
from ctgan.data_sampler import DataSampler

from paradigm.model import ModelFormatOutput, ModelArgs, ModelEnum
from .component import Generator
# 引入日志模块
from logger.logger import logWriter as log


class CTGAN_Model_Instance:
    def __init__(self, model_args: ModelArgs):
        self.name = ModelEnum.CTGAN.name
        self.model_args = model_args
        self.device = self._get_device()
        self.model = self.load()
    def _get_device(self):
        if self.model_args.is_cuda:
            return torch.device("cuda:0")
        else:
            return torch.device("cpu")
    def load(self):
        try:
            checkpoint_path = self.model_args.checkpoint_path
            checkpoint = torch.load(checkpoint_path, weights_only=False, map_location=self.device)
            generator_state = checkpoint['generator_state']
            transformer_config = pickle.loads(checkpoint['transformer_config'])
            metadata = checkpoint['metadata']

            # 初始化 CTGAN 模型
            ctgan = CTGAN(
                embedding_dim=metadata['embedding_dim'],
                generator_dim=metadata['generator_dim'],
                discriminator_dim=metadata['discriminator_dim'],
                batch_size=metadata['batch_size'],
                epochs=metadata['epochs'],
                generator_lr=metadata['generator_lr'],
                discriminator_lr=metadata['discriminator_lr']
            )

            # 恢复 _transformer
            ctgan._transformer = transformer_config

            # 加载 DataSampler
            sampler_file_path = os.path.join(self.model_args.model_path, "sampler")
            with open(sampler_file_path, 'rb') as f:
                data_sampler = pickle.load(f)
            ctgan._data_sampler = data_sampler

            # 动态计算 input_dim 和 data_dim
            embedding_dim = metadata['embedding_dim']
            cond_dim = metadata['cond_dim']  # 从 _data_sampler 获取 cond_dim
            input_dim = embedding_dim + cond_dim
            data_dim = ctgan._transformer.output_dimensions

            # 初始化 Generator
            ctgan._generator = Generator(input_dim, metadata['generator_dim'], data_dim).to(ctgan._device)

            # 加载生成器权重
            ctgan._generator.load_state_dict(generator_state)

            log.write_log("MODEL", "Model successfully loaded from: {}".format(self.model_args.model_path))

            # 保存到实例属性
            return ctgan
        except KeyError as e:
            log.write_log("ERROR", f"Missing key in parameters: {e}")
            raise ValueError(f"Missing key in parameters: {e}")
        except Exception as e:
            log.write_log("ERROR", "Failed to load model from {}: {}".format(self.model_args.model_path, str(e)))
            raise RuntimeError("Failed to load CTGAN model.") from e
    def generate_input(self, params: dict = None):
        if params is None:
            return None, None
        if params["condition_column"] is not None and params["condition_value"] is not None:
            return params["condition_column"], params["condition_value"]
        else:
            return None, None
    def generate_output(self, num_samples=1, params: dict=None) -> ModelFormatOutput:
        """
        使用模型生成输出数据。

        Args:
            output_size (int): 要生成的样本数量，默认值为 1。
            params (dict): ctgan的随机参数，详情参考ctgan.sample

        Returns:
            pd.DataFrame: 生成的合成数据。
        """
        try:
            condition_column, condition_value = self.generate_input(params)
            synthetic_data = self.model.sample(num_samples, condition_column, condition_value)
            log.write_log(
                "MODEL",
                "{} generated output, size: {}".format(self.name, len(synthetic_data))
            )
            return ModelFormatOutput(
                "CTGAN",
                {
                    "condition_column": condition_column,
                    "condition_value": condition_value
                },
                synthetic_data,
                params
            )
        except Exception as e:
            log.write_log(
                "ERROR",
                "{} failed to generate output: {}".format(self.name, str(e))
            )
#             raise RuntimeError("Failed to generate output.") from e
#
#
#
#
#
# class CTGAN_Model_Instance(ABC):
#     def __init__(self, model_path):
#         """
#         初始化 CTGAN 模型实例。
#
#         Args:
#             model_path (str): 所有模型的路径，例如 ROOT_PATH/BHExecutionNode/model/CTGAN。
#         """
#         self.model_path = model_path
#         self.model = None
#
#     def load_model_from_pth_file_path(self, params: dict):
#         """
#         从 .pth 文件加载 CTGAN 模型。
#
#         Args:
#             dir_path (str): 模型文件存放文件夹路径。
#             params (dict): 参数字典，包括以下键：
#                 - "model_name"(str): 模型文件
#                 - "sampler_file_name" (str): DataSampler 的文件名（默认 "sampler"）。
#
#         Returns:
#             None: 直接将加载的模型赋值到实例的 `self.model` 属性。
#         """
#         try:
#             # 设置默认参数
#             default_params = {
#                 "dir_path": "",
#                 "model_name": "model.pth",
#                 "sampler_file_name": "sampler"
#             }
#             if params is None:
#                 params = default_params
#             else:
#                 # 合并默认值和用户提供的值
#                 params = {**default_params, **params}
#
#             # 加载保存的内容
#             dir_path = params["dir_path"]
#             checkpoint_path = os.path.join(self.model_path, dir_path, params["model_name"])
#             checkpoint = torch.load(checkpoint_path, weights_only=False)
#             generator_state = checkpoint['generator_state']
#             transformer_config = pickle.loads(checkpoint['transformer_config'])
#             metadata = checkpoint['metadata']
#
#             # 初始化 CTGAN 模型
#             ctgan = CTGAN(
#                 embedding_dim=metadata['embedding_dim'],
#                 generator_dim=metadata['generator_dim'],
#                 discriminator_dim=metadata['discriminator_dim'],
#                 batch_size=metadata['batch_size'],
#                 epochs=metadata['epochs'],
#                 generator_lr=metadata['generator_lr'],
#                 discriminator_lr=metadata['discriminator_lr']
#             )
#
#             # 恢复 _transformer
#             ctgan._transformer = transformer_config
#
#             # 加载 DataSampler
#             sampler_file_path = os.path.join(self.model_path, dir_path, params["sampler_file_name"])
#             with open(sampler_file_path, 'rb') as f:
#                 data_sampler = pickle.load(f)
#             ctgan._data_sampler = data_sampler
#
#             # 动态计算 input_dim 和 data_dim
#             embedding_dim = metadata['embedding_dim']
#             cond_dim = metadata['cond_dim']  # 从 _data_sampler 获取 cond_dim
#             input_dim = embedding_dim + cond_dim
#             data_dim = ctgan._transformer.output_dimensions
#
#             # 初始化 Generator
#             ctgan._generator = Generator(input_dim, metadata['generator_dim'], data_dim).to(ctgan._device)
#
#             # 加载生成器权重
#             ctgan._generator.load_state_dict(generator_state)
#
#             log.write_log("MODEL", "Model successfully loaded from: {}".format(os.path.join(self.model_path, dir_path)))
#
#             # 保存到实例属性
#             self.model = ctgan
#         except KeyError as e:
#             log.write_log("ERROR", f"Missing key in parameters: {e}")
#             raise ValueError(f"Missing key in parameters: {e}")
#         except Exception as e:
#             log.write_log("ERROR", "Failed to load model from {}: {}".format(dir_path, str(e)))
#             raise RuntimeError("Failed to load CTGAN model.") from e
#
#     def generate_input(self, params=None):
#         """
#         定义生成输入数据的方法。
#
#         Returns:
#             params(dict): 用于生成数据的输入。
#         """
#         if params is None:
#             return None, None
#         if params["condition_column"] is not None and params["condition_value"] is not None:
#             return params["condition_column"], params["condition_value"]
#         else:
#             return None, None
#
#     def generate_output(self, output_size=100, params=None) -> ModelFormatOutput:
#         """
#         使用模型生成输出数据。
#
#         Args:
#             output_size (int): 要生成的样本数量，默认值为 100。
#             params (dict): ctgan的随机参数，详情参考ctgan.sample
#
#         Returns:
#             pd.DataFrame: 生成的合成数据。
#         """
#         try:
#             condition_column, condition_value = self.generate_input(params)
#             synthetic_data = self.model.sample(output_size, condition_column, condition_value)
#             log.write_log(
#                 "MODEL",
#                 "{} generated output, size: {}".format(self.name(), len(synthetic_data))
#             )
#             return ModelFormatOutput(
#                 "CTGAN",
#                 {
#                     "condition_column": condition_column,
#                     "condition_value": condition_value
#                 },
#                 synthetic_data,
#                 params
#             )
#         except Exception as e:
#             log.write_log(
#                 "ERROR",
#                 "{} failed to generate output: {}".format(self.name(), str(e))
#             )
#             raise RuntimeError("Failed to generate output.") from e
#
#     def name(self):
#         """
#         定义模型实例的名称。
#
#         Returns:
#             str: 模型实例的名称。
#         """
#         return "CTGAN_Model_Instance"
