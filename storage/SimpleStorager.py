import base64
import hashlib
import json
import os.path
import pickle
import random
import pandas as pd
import config.config
from logger.logger import logWriter as log
from model.format import ModelFormatOutput
from network.Grpc.FakeGrpc import FakeGrpcEngine
from execution.format import PackedTaskOutput
from storage.encoder.SimpleECHandler import ECHandler
from storage.format import ChunksPoolItem, LoadChunkItem
from utils.function.func import  get_project_root
from config.config import BHExecutionNodeGlobalConfig
# storage提供两个功能
# 1. 将输出ModelFormatOutput.output计算哈希后，分块并生成纠删码
# 2. 存储收到的冗余数据块（包括自己的）
class SimpleStorager:
    def __init__(self, receive_chunks_pool):
        self.storage_path = "" # 存储冗余数据块的路径
        # 这里还需要提供一个索引，用于索引存了哪些冗余块，各个冗余数据块存在哪里，暂时先不管（这里是否应该是在layer2node里存？）
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
    def compute_pco_hash(self, pco: PackedTaskOutput):
        task_sign = pco.sign
        slot = pco.slot
        data = pco.output.output
        task_sign_bytes = str(task_sign).encode('utf-8')
        slot_bytes = str(slot).encode('utf-8')
        data_bytes = pickle.dumps(data)
        hasher = hashlib.sha256()
        hasher.update(task_sign_bytes)
        hasher.update(slot_bytes)
        hasher.update(data_bytes)
        return hasher.hexdigest()
    def compute_chunk_hash(self, chunk):
        hasher = hashlib.sha256()
        hasher.update(chunk)
        return hasher.hexdigest()
    def handle_model_output(self, pco: PackedTaskOutput):
        task_sign = pco.sign
        slot = pco.slot
        data = pco.output.output
        commitment = self.compute_pco_hash(pco) # todo
        encoded_chunks = self.ec_handler.encode(data)
        # 本地先存一个
        local_index = random.randint(0, len(encoded_chunks.chunks) - 1)
        send_indices = []
        send_chunks = []
        # todo 这里的逻辑需要考量 现在只是简单实现
        for i in range(len(encoded_chunks.chunks)):
            if i == local_index:
                self.store_local(BHExecutionNodeGlobalConfig.NODE_ID, task_sign, slot.id, encoded_chunks.chunks[i], i, encoded_chunks.padding_size)
            else:
                send_indices.append(i)
                send_chunks.append(encoded_chunks.chunks[i])
        self.grpc_engine.replicate_encoded_chunks(task_sign, slot.id,send_chunks, send_indices, encoded_chunks.padding_size, False)

        # 这里测试了下如果我要把一些分散的块拿过来然后拼在一起能不能拼回来 逻辑写的比较简单，具体测试多节点的时候应该写的全一点 todo
        local_chunk = self.load_local(BHExecutionNodeGlobalConfig.NODE_ID, task_sign, slot.id, local_index)
        restored_test_data = self.test_collect_process(task_sign, slot.id, local_chunk.data, local_index, encoded_chunks.padding_size)
        pd.testing.assert_frame_equal(restored_test_data, data, check_dtype=False, obj="Decoded Dataframe does not match the origin Dataframe")

        log.write_log("STORAGE", "finish replicate the data from Task {} Slot {}".format(task_sign, slot.id))
        return commitment

    # todo 标准的是这样存文件吗？这样还需要索引吗
    def store_local(self, node_id, sign, slot, chunk, index, padding_size):
        """
        存储分块到本地文件系统。
        :param node_id: 节点 ID
        :param sign: 唯一标识符
        :param slot: 时隙编号
        :param chunk: 分块数据
        :param index: 分块索引
        :param padding_size: 填充的字节数
        """
        # 计算分块的哈希承诺
        commitment = self.compute_chunk_hash(chunk)

        # 构建分级存储路径
        file_dir = os.path.join(self.storage_path, str(sign), str(slot), f"node_{node_id}")
        file_path = os.path.join(file_dir, f"{index}-chunk.json")

        # 确保存储路径存在
        os.makedirs(file_dir, exist_ok=True)
        # 这里json没法存bytes，后面读出来的时候需要用base64再转回bytes
        chunk_base64 = base64.b64encode(chunk).decode('utf-8')
        # 构造存储数据
        chunk_data = {
            "data": chunk_base64,
            "padding": padding_size,
            "commitment": commitment
        }

        # 写入文件
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(chunk_data, f, ensure_ascii=False, indent=4)
                f.close()
        except Exception as e:
            raise IOError(f"Failed to store chunk locally at {file_path}: {e}")
        # todo 逻辑考量
        self.grpc_engine.send_store_message(node_id, sign, slot, node_id, index, padding_size)
        # 写日志
        log.write_log("STORAGE", f"Chunk stored locally: {file_path}")
    # todo 同上
    # 这里读出chunk的内容，自己先检查一遍完整性（其实也不需要，外面可能还要检查一遍？）
    def load_local(self, node_id, sign, slot, index):
        """
        从本地文件系统加载指定分块。
        :param node_id: 节点 ID
        :param sign: 唯一标识符
        :param slot: 时隙编号
        :param index: 分块索引
        :return: 包含分块数据、填充大小和哈希承诺的字典
        """
        # 构建文件路径
        file_dir = os.path.join(self.storage_path, str(sign), str(slot), f"node_{node_id}")
        file_path = os.path.join(file_dir, f"{index}-chunk.json")

        # 检查文件是否存在
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Chunk file not found: {file_path}")

        # 读取文件内容
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                chunk_data = json.load(f)
        except Exception as e:
            raise IOError(f"Failed to load chunk file at {file_path}: {e}")

        # 解码 Base64 数据
        try:
            chunk = base64.b64decode(chunk_data["data"])
        except Exception as e:
            raise ValueError(f"Failed to decode chunk data from Base64: {e}")
        commitment = self.compute_chunk_hash(chunk)
        # 说明数据被篡改
        if commitment != chunk_data["commitment"]:
            raise ValueError("chunk data has been modified, {} != {}".format(commitment, chunk_data["commitment"]))
        return LoadChunkItem(node_id, sign, slot, index, chunk, commitment, chunk_data["padding"])

    def start(self):
        pass


    def set_grpc(self, grpc_engine):
        self.grpc_engine = grpc_engine



    # 模拟下一个collect的过程，为了拿到本地的就在这边简单模拟下
    # 模拟下要收集这个节点在sign slot里合成的数据块
    def test_collect_process(self, sign, slot, local_chunk, index, padding_size):
        chunks, indices = self.grpc_engine.start_test_collect_process(BHExecutionNodeGlobalConfig.NODE_ID, sign, slot)
        # 先试试直接合
        if len(chunks) < BHExecutionNodeGlobalConfig.EC_PARAMS_K:
            chunks.append(local_chunk)
            indices.append(index)
        return self.ec_handler.decode(chunks, indices, padding_size)