"""
    NOTE: Processor 对那些unprocessed的slot进行处理
    可以使用worker来进行并行
"""
import threading

from config.config import BHExecutionNodeGlobalConfig
from queue import Queue

from model.loader import ModelLoader
from paradigm.model import ModelEnum, CommitSlotModelParams
from paradigm.slot import CommitSlotItem

from concurrent.futures import ThreadPoolExecutor, as_completed

from storage.Storager import Storager
from utils.function.func import get_model_root
from logger.logger import logWriter as log


class Processor:
    def __init__(self):
        # self.num_workers = BHExecutionNodeGlobalConfig.NUM_PROCESS_WORKER TODO @SD 这里补上这个然后把下面一行注释掉
        self.num_workers = 2
        self.storager: Storager = None
        # self.slot_channel = slot_channel # 传递给slotManager 这里不需要传递，是storager传递
        self.unprocessed_queue = Queue()
        # self.model_instances = []
        self.model_instances = {}
    def set_storager(self, storager: Storager):
        self.storager = storager
    def load_model_instance(self):
        # todo 这里要把所有支持的模型全部load进来
        model_path = get_model_root()
        log.write_log("INFO", "Init Processor with model from {}".format(model_path))
        loader = ModelLoader(model_path)
        self.model_instances = loader.load_all_model_support()
    def process_unprocessed_slot(self, slot: CommitSlotItem):
        if not slot.is_unprocess():
            raise ValueError("The slot processed in Processor must in Unprocessed State!!!")
        self.unprocessed_queue.put(slot)
    def start(self):
        self.load_model_instance()
        for i in range(self.num_workers):
            thread = threading.Thread(target=self.worker)
            thread.start()
        # with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
        #     futures = [executor.submit(self.worker) for _ in range(self.num_workers)]
        #     for future in as_completed(futures):
        #         try:
        #             future.result()
        #         except Exception as e:
        #             print(f"Worker failed: {e}")
    def worker(self):
        while True:
            try:
                # 使用阻塞模式从队列中获取元素
                slot: CommitSlotItem = self.unprocessed_queue.get(block=True)  # 阻塞直到有可用数据或超时
                params: CommitSlotModelParams = slot.params
                if params.name not in self.model_instances:
                    # 如果不支持这一模型
                    raise ValueError("{} Model is not supported!!!".format(params.name))

                # TODO @YZM
                model_instance = self.model_instances[params.name]  # 获取预先加载好的模型
                output = model_instance.generate_output(slot.size, params.condition_params)  # 调用模型得到输出
                self.storager.handle_slot_output(slot, output)  # 将输出和slot交给storager

            except Exception as e:
                log.write_log("ERROR", f"Worker encountered an error: {e}")

