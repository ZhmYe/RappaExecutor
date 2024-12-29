import argparse
from network.Grpc.grpc_engine import GrpcEngine
from queue import Queue
from logger.logger import logWriter as log
from storage.Storager import Storager
from config.config import BHExecutionNodeGlobalConfig
from processor.processor import Processor
from task.SlotManager import SlotManager
from task.TaskTracker import TaskTracker


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
    # add by zhmye
    # 这里将config.json作为参数传入
    parser.add_argument(
        "--config",
        default="config.json",
        type=str,
        help="Enable config loading. Loading Config from the given path."
    )
    return parser.parse_args()


def load_config(config_path):
    BHExecutionNodeGlobalConfig.load_config(config_path)
    log.init()


def init_pool() -> Queue:
    return Queue()


def init_grpc_engine(pending, finish, chunks, slot_channel) -> GrpcEngine:
    grpc_engine = GrpcEngine(pending, finish, chunks, slot_channel)
    grpc_engine.load_config()
    return grpc_engine


def init_storager(slot_channel, chunks) -> Storager:
    s = Storager(slot_channel, chunks)
    # s.load_config()
    return s


if __name__ == '__main__':
    # 解析命令行参数
    args = parse_args()
    load_config(args.config)  # 解析参数
    # 根据命令行参数设置全局调试模式
    BHExecutionNodeGlobalConfig.set_debug(args.debug)

    # 初始化grpc，所有公用
    pending_task_pool = init_pool()
    finish_task_pool = init_pool()
    receive_chunks_pool = init_pool()
    slot_channel = init_pool()
    grpc_engine = init_grpc_engine(pending_task_pool, finish_task_pool, receive_chunks_pool, slot_channel)
    # 初始化存储模块
    storager = init_storager(slot_channel, receive_chunks_pool)
    storager.set_grpc(grpc_engine)

    # Processor
    processor = Processor()
    processor.set_storager(storager)

    slot_manager = SlotManager(slot_channel)
    slot_manager.set_processor(processor=processor)
    slot_manager.set_grpc_engine(grpc_engine=grpc_engine)

    task_tracker = TaskTracker(pending_task_pool)
    task_tracker.set_slot_manager(slot_manager)


    # # 初始化合成节点
    # node = BHExecutionNode(pending_task_pool, finish_task_pool)
    # node.load_config()
    # node.set_grpc_engine(grpc_engine)
    # node.set_storager(storager)
    # 启动grpc
    grpc_engine.start_all()

    storager.start()
    processor.start()
    task_tracker.start()
    slot_manager.start()
    # node.start()
