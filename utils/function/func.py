import argparse
import os
from multiprocessing import Queue



# 这里放一些可以修改的用户定义的函数，比如路径什么的

def get_project_root():
    """
    Get the root directory of the project by searching for a specific marker file.
    """
    current_dir = os.path.abspath(os.path.dirname(__file__))
    while current_dir != os.path.dirname(current_dir):  # Stop at filesystem root
        if ".project_root" in os.listdir(current_dir):  # Check for marker file
            return current_dir
        current_dir = os.path.dirname(current_dir)
    raise FileNotFoundError("Project root marker file not found.")

def get_model_root():
    project_root = get_project_root()
    return os.path.join(project_root, 'model')

def get_model_params_dict(model_name):
    model_dict = {
        "CTGAN": {
            "dir_path": "test",
            "model_name": "ctgan_model.pth",
            "sampler_file_name": "sampler"
        }
    }
    if model_dict.get(model_name) is None:
        raise ValueError("model dict didn't save the model {}, please modify model_dict in utils/function/func.py".format(model_name))
    return model_dict[model_name]


def parse_args():
    """
    解析命令行参数
    """
    parser = argparse.ArgumentParser(description="BHExecutionNode Configuration")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode. Logs will not be saved to files."
    )
    parser.add_argument(
        "--store",
        default="ec",
        type=str,
        help="Given file storage method: ec, local, replicas"
    )
    # add by zhmye
    # 这里将config.json作为参数传入
    parser.add_argument(
        "--config",
        default="~/rappa/RappaMaster/config.json",
        type=str,
        help="Enable config loading. Loading Config from the given path."
    )
    parser.add_argument(
        "--cuda",
        action="store_true",
        help="Enable cuda. Model will generate output in cuda." # todo 已经在model里写好了，但是还没完全适配
    )
    return parser.parse_args()


def init_pool() -> Queue:
    return Queue()