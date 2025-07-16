import argparse
import os
from multiprocessing import Queue
import requests
import json
import os
from logger.logger import logWriter as log


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
        default="local",
        type=str,
        help="Given file storage method: ec, local, replicas"
    )
    # add by zhmye
    # 这里将config.json作为参数传入
    parser.add_argument(
        "--config",
        default="config.json",
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


def trigger_zkml_proof(slot, zkml_config):
    """
    向 BH-ZKML 服务发送一个异步的证明生成请求 (fire-and-forget)。

    Args:
        slot (CommitSlotItem): 当前正在处理的 Slot 对象。
        zkml_config (dict): 包含 ZKML 服务相关配置的字典。
    """
    # 需要在config中配置
    zkml_url = zkml_config.get("url")
    input_file_path = zkml_config.get("input_file")

    if not zkml_url or not input_file_path:
        log.write_log("ERROR", "ZKML URL or input file path not configured. Skipping proof trigger.")
        return

    if not os.path.exists(input_file_path):
        log.write_log("ERROR", f"ZKML input file not found at: {input_file_path}. Skipping proof trigger.")
        return

    # 3. 构建请求体 (payload)
    # ZKML 服务需要 sign 和 slot，从传入的 slot 对象中获取
    payload = {
        "input_file_name": input_file_path,
        "sign": str(slot.sign),
        "slot": int(slot.slot) 
    }

    # 4. 发送异步请求
    try:
        log.write_log("EXECUTION", f"Triggering ZKML proof for Slot {slot.sign}/{slot.slot} to {zkml_url}")
        requests.post(
            zkml_url, 
            data=json.dumps(payload), 
            headers={"Content-Type": "application/json"}, 
            timeout=0.5  # 设置短暂的超时
        )
        log.write_log("EXECUTION", f"ZKML proof trigger request completed for Slot {slot.sign}/{slot.slot}.")
    
    except requests.exceptions.Timeout:
        log.write_log("EXECUTION", f"Successfully triggered ZKML proof for Slot {slot.sign}/{slot.slot} (fire-and-forget).")
    
    except requests.exceptions.RequestException as e:
        log.write_log("ERROR", f"Failed to trigger ZKML proof for Slot {slot.sign}/{slot.slot}. Error: {e}")