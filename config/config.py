import json
import os
from utils.function.func import get_project_root
from config.default import DEFAULT_NODE_ID, DEFAULT_RS_CODE_N, DEFAULT_RS_CODE_K, DEFAULT_GRPC_PORT, DEFAULT_NODE_IP, \
    DEFAULT_LAYER2NODE_IP, DEFAULT_LAYER2NODE_PORT, DEFAULT_STORAGE_PATH, DEFAULT_LOG_PATH, DEFAULT_NUM_PROCESS_WORKER, \
    DEFAULT_REDUNDANCY, DEFAULT_OTHER_NODE_GRPC_ADDRESSES, DEFAULT_ALL_NODE_NUM


# def load_config(config_file_path):
#     """
#     从指定的 (JSON 或 INI)配置文件加载配置到全局配置类
#     """
#     if not os.path.exists(config_file_path):
#         raise FileNotFoundError(f"config file not exists: {config_file_path}")

#     ext = os.path.splitext(config_file_path)[-1].lower()
#     if ext == ".json":
#         with open(config_file_path, "r") as config_file:
#             config_data = json.load(config_file)
#     elif ext == ".ini":
#         config = configparser.ConfigParser()
#         config.read(config_file_path)
#         config_data = {key: _convert_value(value) for key, value in config["DEFAULT"].items()}
#     else:
#         raise ValueError("Unsupported configuration file format. Please use a .json or .ini file.")

#     for key, value in config_data.items():
#         if hasattr(BHExecutionNodeGlobalConfig, key):
#             setattr(BHExecutionNodeGlobalConfig, key, value)

# TODO @SD 这里需要全局的所有节点address和master本质上一样
class BHExecutionNodeGlobalConfig:
    DEBUG = False  # 全局调试模式，默认关闭
    NODE_ID = DEFAULT_NODE_ID
    # EC
    EC_PARAMS_N = DEFAULT_RS_CODE_N
    EC_PARAMS_K = DEFAULT_RS_CODE_K

    # 通讯节点地址（不包括自己）
    OTHER_NODE_GRPC_ADDRESSES = DEFAULT_OTHER_NODE_GRPC_ADDRESSES

    # 节点总数
    ALL_NODE_NUM = DEFAULT_ALL_NODE_NUM

    NODE_IP = DEFAULT_NODE_IP
    GRPC_PORT = DEFAULT_GRPC_PORT

    LAYER2_ADDRESS_IP = DEFAULT_LAYER2NODE_IP
    LAYER_ADDRESS_PORT = DEFAULT_LAYER2NODE_PORT

    NUM_PROCESS_WORKER = DEFAULT_NUM_PROCESS_WORKER

    REDUNDANCY = DEFAULT_REDUNDANCY

    STORAGE_PATH = DEFAULT_STORAGE_PATH
    LOG_PATH = DEFAULT_LOG_PATH

    @classmethod
    def set_debug(cls, debug):
        """
        根据命令行参数设置全局调试模式
        """
        cls.DEBUG = debug

    @classmethod
    def print_config(cls):
        """
        打印所有全局配置信息
        """
        config_info = {
            "DEBUG": cls.DEBUG,
            "NODE_ID": cls.NODE_ID,
            "EC_PARAMS_N": cls.EC_PARAMS_N,
            "EC_PARAMS_K": cls.EC_PARAMS_K,
            "NODE_IP": cls.NODE_IP,
            "GRPC_PORT": cls.GRPC_PORT,
            "LAYER2_ADDRESS_IP": cls.LAYER2_ADDRESS_IP,
            "LAYER_ADDRESS_PORT": cls.LAYER_ADDRESS_PORT,
            "OTHER_NODE_GRPC_ADDRESSES": cls.OTHER_NODE_GRPC_ADDRESSES,
            "ALL_NODE_NUM": cls.ALL_NODE_NUM,
            "NUM_PROCESS_WORKER": cls.NUM_PROCESS_WORKER,
            "REDUNDANCY": cls.REDUNDANCY,
            "STORAGE_PATH": cls.STORAGE_PATH,
            "LOG_PATH": cls.LOG_PATH
        }

        print("BHExecutionNodeGlobalConfig info:")
        print("=" * 50)
        for key, value in config_info.items():
            print(f"{key}: {value}")

    @classmethod
    def load_config(cls, config_file_path):
        """
        从配置文件加载并更新全局配置
        """
        try:
            config_file_path = os.path.join(get_project_root(), config_file_path)
            with open(config_file_path, 'r') as f:
                config_data = json.load(f)

            # 更新类的属性
            for key, value in config_data.items():
                if hasattr(cls, key):
                    setattr(cls, key, value)

            setattr(cls, 'ALL_NODE_NUM', len(cls.OTHER_NODE_GRPC_ADDRESSES) + 1)

            print(f"Configuration loaded from {config_file_path}")
        except Exception as e:
            print(f"Error loading configuration: {e},use default configuration")
