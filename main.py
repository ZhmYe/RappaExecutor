import argparse
from multiprocessing import Process, Queue, Manager

from mocker.mocker_collector import MockerCollector
from network.Grpc.grpc_engine import GrpcEngine
# from queue import Queue
from logger.logger import logWriter as log
from paradigm.channel import Channel
from storage.Storager import Storager
from config.config import BHExecutionNodeGlobalConfig
from processor.processor import Processor
from storage.receiver.SimpleReceiver import SimpleReceiver
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



if __name__ == '__main__':

# 解析命令行参数
    args = parse_args()
    load_config(args.config)  # 解析参数
    # 根据命令行参数设置全局调试模式
    BHExecutionNodeGlobalConfig.set_debug(args.debug)
    # 定义所有的channel
    manager = Manager()
    channel = Channel(manager)


    # ===================================== TaskTracker,用于标识本地收到了哪些任务 =====================================
    # to_task_tracker_channel = Queue()
    task_tracker = TaskTracker(channel=channel)

    # ===================================== SlotManager, Slot全生命周期管理 =====================================
    # to_slot_manager_channel = init_pool()
    slot_manager = SlotManager(channel=channel)
    # SlotManager需要与TaskTracker交互
    # slot_manager.set_to_task_tracker_channel(to_task_tracker_channel=to_task_tracker_channel)

    # ===================================== Grpc Engine, 管理Grpc Server和Grpc Client =====================================
    grpc_engine = GrpcEngine(channel=channel)

    # ===================================== Storager, 管理存储(纠删码生成和冗余块存储) =====================================
    storager = Storager(channel=channel)

    # ===================================== Processor, 管理model, 生成输出 =====================================
    processor = Processor(channel=channel)
    # ===================================== Receiver, 接收冗余块，存储 =====================================
    receiver = SimpleReceiver(channel=channel)


    # ===================================== Collector, 测试恢复ec块, 仅用于测试 =====================================
    collector = MockerCollector(channel=channel)

    processes = [
        Process(target=grpc_engine.start_all),
        Process(target=storager.start),
        Process(target=processor.start),
        Process(target=task_tracker.start),
        Process(target=slot_manager.start),
        Process(target=collector.start),
        Process(target=receiver.start)
    ]

    # 启动所有进程
    for process in processes:
        process.start()

    # 等待所有进程完成
    for process in processes:
        process.join()