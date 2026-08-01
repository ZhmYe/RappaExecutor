"""
    NOTE: Processor 对那些unprocessed的slot进行处理
    可以使用worker来进行并行
"""
"""
    NOTE: Processor 对那些unprocessed的slot进行处理
    可以使用worker来进行并行
"""
import torch.cuda
import time
import torch  # 确保能识别 Tensor 类型
import networkx as nx
import pickle
from datetime import datetime  # 引入 datetime 模块处理毫秒
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
                
                # ==================== 修改开始时间为毫秒 ====================
                start_time = time.time()
                start_time_str = datetime.fromtimestamp(start_time).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                # 写入日志
                log.write_log("INFO", f"Slot {slot.hash}, start_time: {start_time_str}")
                
                output = model_instance.generate_output(slot.size, params.condition_params)  # 调用模型得到输出
                
                 # 计算数据量大小 (byte)
                data = output.output
                if params.name == 'BAED':
                    # 图数据使用 pickle 估算大小
                    data_size = len(pickle.dumps(output))
                else:
                    # 其他数据使用指定的计算方式
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
                        
                # ==================== 修改结束时间为毫秒 ====================
                end_time = time.time()
                end_time_str = datetime.fromtimestamp(end_time).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                
                log.write_log("INFO", f"Slot {slot.hash} total size: {data_size} bytes, end_time:  {end_time_str}")
                speed = data_size / (end_time - start_time)
                self.channel.latest_synth_speed.value = speed
                slot.upload_size = int(data_size)
                slot.speed = speed

                # 1. 记录原始合成样本数 (size)，确保 Master 进度条显示正确
                if isinstance(output.output, list):
                    slot.process = len(output.output)
                elif hasattr(output.output, 'shape'): # 兼容 DataFrame
                    slot.process = len(output.output)
                else:
                    slot.process = slot.size

                # 2. 适配图数据格式：合并所有子图并清理 Tensor
                if params.name == 'BAED' and isinstance(data, list) and len(data) > 0 and isinstance(data[0], nx.Graph):
                    combined_graph = nx.Graph()
                    for graph in data:
                        combined_graph = nx.compose(combined_graph, graph)
                    # 深度清理合并后图中的 Tensor
                    for node, attrs in combined_graph.nodes(data=True):
                        for key, val in list(attrs.items()):
                            if torch.is_tensor(val):
                                attrs[key] = val.item() if val.numel() == 1 else val.detach().cpu().tolist()
                    
                    for u, v, attrs in combined_graph.edges(data=True):
                        for key, val in list(attrs.items()):
                            if torch.is_tensor(val):
                                attrs[key] = val.item() if val.numel() == 1 else val.detach().cpu().tolist()

                    # 转换为标准字典格式
                    graph_dict = nx.node_link_data(combined_graph)
                    
                    # 包装为列表输出。注意：虽然此处列表长度为 1，但 slot.process 已经保留了原始样本数。
                    output.output = [graph_dict]
                # self.storager.handle_slot_output(slot, output)  # 将输出和slot交给storager
                self.channel.to_storager_slot_channel.put((slot, output))
            except Exception as e:
                log.write_log("ERROR", f"Processor cycle error: {e}")
                raise RuntimeError(e)

    def start(self):
        self.load_model_instance()
        self.process_unprocessed_slot()
