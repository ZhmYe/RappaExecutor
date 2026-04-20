"""
    NOTE: Processor 对那些unprocessed的slot进行处理
    可以使用worker来进行并行
"""
import torch.cuda
import time
from config.config import BHExecutionNodeGlobalConfig
from model.loader import ModelLoader
from paradigm.channel import Channel
from paradigm.model import CommitSlotModelParams
from paradigm.slot import CommitSlotItem

from utils.function.func import get_model_root
from logger.logger import logWriter as log


class Processor:
    def __init__(self, channel: Channel):
        self.num_workers = BHExecutionNodeGlobalConfig.NUM_PROCESS_WORKER
        # self.num_workers = 1
        # self.storager: Storager = None
        self.channel = channel
        # self.slot_channel = slot_channel # 传递给slotManager 这里不需要传递，是storager传递
        # self.unprocessed_queue = Queue()
        # self.model_instances = []
        self.model_instances = {}

    # def set_storager(self, storager: Storager):
    #     self.storager = storager
    def load_model_instance(self):
        # todo 这里要把所有支持的模型全部load进来
        model_path = get_model_root()
        log.write_log("INFO", "Init Processor with model from {}".format(model_path))
        loader = ModelLoader(model_path)
        self.model_instances = loader.load_all_model_support(is_cuda=BHExecutionNodeGlobalConfig.IS_CUDA)

    def process_unprocessed_slot(self):
        while True:
            try:
                if self.channel.to_processor_slot_channel.empty():
                    continue
                slot: CommitSlotItem = self.channel.to_processor_slot_channel.get(timeout=0.01)
                if not slot.is_unprocess():
                    raise ValueError("The slot processed in Processor must in Unprocessed State!!!")
                # self.channel.to_worker_slot_channel.put(slot)
                params: CommitSlotModelParams = slot.params
                if params.name not in self.model_instances:
                    # 如果不支持这一模型
                    raise ValueError("{} Model is not supported!!!".format(params.name))

                # TODO @YZM
                model_instance = self.model_instances[params.name]  # 获取预先加载好的模型
                start_time = time.time()
                output = model_instance.generate_output(slot.size, params.condition_params)  # 调用模型得到输出
                duration = time.time() - start_time
                
                # 计算速度 (byte/s)
                speed = 0.0
                if duration > 0:
                    # output 是 ModelFormatOutput 类型，真实数据在 output.output 中
                    data = output.output
                    
                    # 估算字节大小
                    data_size = 0
                    if isinstance(data, (bytes, bytearray)):
                        data_size = len(data)
                    elif isinstance(data, str):
                        data_size = len(data.encode('utf-8'))
                    elif hasattr(data, 'to_json'): # Pandas DataFrame
                        # 转换成 json 估算大小，这与 Storager 的存储逻辑一致
                        data_size = len(data.to_json().encode('utf-8'))
                    elif isinstance(data, list):
                        try:
                            import json
                            data_size = len(json.dumps(data).encode('utf-8'))
                        except:
                            data_size = len(str(data))
                    else:
                        data_size = len(str(data))
                        
                    speed = data_size / duration
                
                log.write_log("INFO", f"Slot {slot.hash} synth speed: {speed:.2f} byte/s, total size: {data_size} bytes, time: {duration:.4f}s")
                self.channel.latest_synth_speed.value = speed
                slot.upload_size = int(data_size)

                # self.storager.handle_slot_output(slot, output)  # 将输出和slot交给storager
                self.channel.to_storager_slot_channel.put((slot, output))
            except Exception as e:
                log.write_log("ERROR", f"Processor cycle error: {e}")
                raise RuntimeError(e)

    def start(self):
        self.load_model_instance()
        self.process_unprocessed_slot()
        # processes = [
        #     Process(target=self.process_unprocessed_slot)
        # ]
        # # for i in range(self.num_workers):
        # #     processes.append(Process(target=self.worker))
        #     # thread = threading.Thread(target=self.worker)
        #     # thread.start()
        # for process in processes:
        #     process.start()
        # for process in processes:
        #     process.join()
        # with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
        #     futures = [executor.submit(self.worker) for _ in range(self.num_workers)]
        #     for future in as_completed(futures):
        #         try:
        #             future.result()
        #         except Exception as e:
        #             print(f"Worker failed: {e}")
    # def worker(self):
    #     while True:
    #         try:
    #             # 使用阻塞模式从队列中获取元素
    #             if self.channel.to_worker_slot_channel.empty():
    #                 continue
    #             slot: CommitSlotItem = self.channel.to_worker_slot_channel.get(timeout=1)  # 阻塞直到有可用数据或超时
    #             params: CommitSlotModelParams = slot.params
    #             if params.name not in self.model_instances:
    #                 # 如果不支持这一模型
    #                 raise ValueError("{} Model is not supported!!!".format(params.name))
    #
    #             # TODO @YZM
    #             model_instance = self.model_instances[params.name]  # 获取预先加载好的模型
    #             # startTime = time.time()
    #             output = model_instance.generate_output(slot.size, params.condition_params)  # 调用模型得到输出
    #             # print(time.time() - startTime)
    #             # self.storager.handle_slot_output(slot, output)  # 将输出和slot交给storager
    #             self.channel.to_storager_slot_channel.put((slot, output))
    #
    #         except Exception as e:
    #             log.write_log("ERROR", f"Worker encountered an error: {e}")
