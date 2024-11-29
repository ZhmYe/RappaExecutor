import argparse
import threading
from network.Grpc.Grpc import GrpcEngine
from queue import Queue
from logger.logger import logWriter as log
from execution.node import BHExecutionNode
from storage.SimpleStorager import SimpleStorager as Storager
from config.config import BHExecutionNodeGlobalConfig

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
    return parser.parse_args()
def load_config(config_path):
    BHExecutionNodeGlobalConfig.load_config(config_path)
    log.init()

def init_pool()->Queue:
    return Queue()
def init_grpc_engine(pending, finish, chunks)->GrpcEngine:
    grpc_engine = GrpcEngine(pending, finish, chunks)
    grpc_engine.load_config()
    return grpc_engine
def init_storager(chunks)->Storager:
    s = Storager(chunks)
    s.load_config()
    return s
if __name__ == '__main__':
    # 解析命令行参数
    args = parse_args()
    load_config("config.json") # 解析参数
    # 根据命令行参数设置全局调试模式
    BHExecutionNodeGlobalConfig.set_debug(args.debug)

    # 初始化grpc，所有公用
    pending_task_pool = init_pool()
    finish_task_pool = init_pool()
    receive_chunks_pool = init_pool()
    grpc_engine = init_grpc_engine(pending_task_pool, finish_task_pool, receive_chunks_pool)
    # 初始化存储模块
    storager = init_storager(receive_chunks_pool)
    storager.set_grpc(grpc_engine)

    # 初始化合成节点
    node = BHExecutionNode(pending_task_pool, finish_task_pool)
    node.load_config()
    node.set_grpc_engine(grpc_engine)
    node.set_storager(storager)

    grpc_thread = threading.Thread(target=grpc_engine.start_server)
    grpc_thread.start() # 启动grpc
    node.start()