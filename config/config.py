import json
import os
from enum import Enum, auto
from utils.function.func import get_project_root
from config.default import DEFAULT_NODE_ID, DEFAULT_RS_CODE_N, DEFAULT_RS_CODE_K, DEFAULT_GRPC_PORT, DEFAULT_NODE_IP, \
    DEFAULT_LAYER2NODE_IP, DEFAULT_LAYER2NODE_PORT, DEFAULT_STORAGE_PATH, DEFAULT_LOG_PATH, DEFAULT_NUM_PROCESS_WORKER, \
    DEFAULT_REDUNDANCY, DEFAULT_OTHER_NODE_GRPC_ADDRESSES, DEFAULT_ALL_NODE_NUM, DEFAULT_IS_RECOVERY,DEFAULT_CERT_PATH


class STORE_METHOD_ENUM(Enum):
    LOCAL = auto()
    REPLICAS = auto()
    EC = auto()

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


    CERT_PATH=DEFAULT_CERT_PATH

    STORAGE_PATH = DEFAULT_STORAGE_PATH
    ABMStockDataDir = "/root/rappa/stockdata"
    ABMStockParamDir = "/root/rappa/stockdata/params"
    IS_RECOVERY = DEFAULT_IS_RECOVERY
    LOG_PATH = DEFAULT_LOG_PATH
    STORE_METHOD = STORE_METHOD_ENUM.LOCAL
    IS_CUDA = False

    @classmethod
    def set_debug(cls, debug):
        """
        根据命令行参数设置全局调试模式
        """
        cls.DEBUG = debug
    @classmethod
    def enable_cuda(cls):
        cls.IS_CUDA = True
    @classmethod
    def set_store_method(cls, method):
        if method == "ec":
            cls.STORE_METHOD = STORE_METHOD_ENUM.EC
        elif method == "local":
            cls.STORE_METHOD = STORE_METHOD_ENUM.LOCAL
        elif method == "replicas":
            cls.STORE_METHOD = STORE_METHOD_ENUM.REPLICAS
        else:
            # 默认为ec
            cls.STORE_METHOD = STORE_METHOD_ENUM.EC
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
            "IsRecovery": cls.IS_RECOVERY,
            "LAYER2_ADDRESS_IP": cls.LAYER2_ADDRESS_IP,
            "LAYER_ADDRESS_PORT": cls.LAYER_ADDRESS_PORT,
            "OTHER_NODE_GRPC_ADDRESSES": cls.OTHER_NODE_GRPC_ADDRESSES,
            "ALL_NODE_NUM": cls.ALL_NODE_NUM,
            "NUM_PROCESS_WORKER": cls.NUM_PROCESS_WORKER,
            "REDUNDANCY": cls.REDUNDANCY,
            "STORAGE_PATH": cls.STORAGE_PATH,
            "ABMStockDataDir": cls.ABMStockDataDir,
            "ABMStockParamDir": cls.ABMStockParamDir,
            "CERT_PATH": cls.CERT_PATH,
            "LOG_PATH": cls.LOG_PATH
        }

        print("BHExecutionNodeGlobalConfig info:")
        print("=" * 50)
        for key, value in config_info.items():
            print(f"{key}: {value}")

    @classmethod
    def load_config(cls, args):
        """
        从配置文件加载并更新全局配置
        """
        try:
            config_file_path = os.path.join(get_project_root(), args.config)
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
        cls.set_store_method(args.store)
        cls.set_debug(args.debug)
        if args.cuda:
            cls.enable_cuda()
        cls.print_config()
