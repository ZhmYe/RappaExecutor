import os.path
import random

import config.config
from logger.logger import logWriter as log
from model.format import ModelFormatOutput
from network.Grpc.FakeGrpc import FakeGrpcEngine
from execution.format import PackedTaskOutput
from storage.encoder.SimpleECHandler import ECHandler
from storage.format import ChunksPoolItem
from utils.function.func import  get_project_root
from config.config import BHExecutionNodeGlobalConfig
# storage提供两个功能
# 1. 将输出ModelFormatOutput.output计算哈希后，分块并生成纠删码
# 2. 存储收到的冗余数据块（包括自己的）
class Storager:
    def __init__(self, receive_chunks_pool):
        self.storage_path = "" # 存储冗余数据块的路径
        # 这里还需要提供一个索引，用于索引各个冗余数据块存在哪里，暂时先不管
        # 另外，冗余数据块索引还需要进行持久化，不然down了就没有索引了，用追加日志的方式 todo
        self.index = {}
        # self.send_chunks_pool = send_chunks_pool # 用来存储需要被发送给其它节点的chunk
        self.receive_chunks_pool = receive_chunks_pool # 用来存储收到的来自其它节点的chunk
        self.ec_handler:ECHandler = None # 纠删码
        self.grpc_engine: FakeGrpcEngine = None
    def load_config(self):
        self.storage_path = os.path.join(get_project_root(), BHExecutionNodeGlobalConfig.STORAGE_PATH)
        log.write_log("INFO", "Init Storager from config, storage_path: {}".format(self.storage_path))
        self.ec_handler = ECHandler(BHExecutionNodeGlobalConfig.EC_PARAMS_K, BHExecutionNodeGlobalConfig.EC_PARAMS_N)
    def compute_hash(self, output: ModelFormatOutput):
        return ""
    def handle_model_output(self, pco: PackedTaskOutput):
        task_sign = pco.sign
        slot = pco.slot
        data = pco.output.output
        commitment = self.compute_hash(pco.output) # todo
        encoded_chunks = self.ec_handler.encode(data)
        # 本地先存一个
        local_index = random.randint(0, len(encoded_chunks.chunks))
        send_indices = []
        send_chunks = []
        for i in range(len(encoded_chunks.chunks)):
            if i == local_index:
                self.store_local(BHExecutionNodeGlobalConfig.NODE_ID, task_sign, slot.id, encoded_chunks.chunks[i], i, encoded_chunks.padding_size)
            else:
                send_indices.append(i)
                send_chunks.append(encoded_chunks.chunks[i])
        # todo 这里的逻辑需要考量
        self.grpc_engine.replicate_encoded_chunks(task_sign, slot.id,send_chunks, send_indices, encoded_chunks.padding_size, False)
        log.write_log("STORAGE", "finish replicate the data from Task {} Slot {}".format(task_sign, slot.id))
        return commitment
    def store_local(self, node_id, sign, slot, chunk, index, padding_size):
        # todo 这里写文件
        log.write_log("STORAGE", "storage a file to local, from execution {} task {} slot {}, chunk data: {}, chunk index: {}, padding_size:{}".format(node_id, sign, slot, chunk, index, padding_size))
    def start(self):
        pass


    def set_grpc(self, grpc_engine):
        self.grpc_engine = grpc_engine

