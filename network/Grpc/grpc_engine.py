from queue import Queue
import threading
from typing import Optional

from mocker.exection_node import MockerNode
from config.config import BHExecutionNodeGlobalConfig
from logger.logger import logWriter as log
from mocker.layer2node import MockerLayer2nNode
from network.Grpc.grpc_client import GrpcClient
from network.Grpc.grpc_config import GrpcConfig
from network.Grpc.grpc_server import GrpcServer

from network.format import BHExecutionAddress


class GrpcEngine:
    def __init__(self, pending_task_pool=Queue(), finish_task_pool=Queue(), receive_chunks_pool=Queue()) -> None:
        # 当前的grpc配置信息
        self.config = GrpcConfig()
        # 设置队列
        self.config.pending_task_pool = pending_task_pool
        self.config.finish_task_pool = finish_task_pool
        self.config.receive_chunks_pool = receive_chunks_pool
        # 当前的grpc服务端
        self.server: Optional[GrpcServer] = None
        # 当前的grpc客户端
        self.client: Optional[GrpcClient] = None

        # todo ==============暂未实现部分，使用fake替代==========================
        self.fake_layer2_node = None
        self.fake_other_nodes = {}

    # 加载配置
    def load_config(self):
        # 导入本机和layer2端地址和端口
        self.config.address = BHExecutionAddress(BHExecutionNodeGlobalConfig.NODE_IP,
                                                 BHExecutionNodeGlobalConfig.GRPC_PORT)
        self.config.layer2_address = BHExecutionAddress(BHExecutionNodeGlobalConfig.LAYER2_ADDRESS_IP,
                                                        BHExecutionNodeGlobalConfig.LAYER_ADDRESS_PORT)
        # 导入节点id
        self.config.node_id = str(BHExecutionNodeGlobalConfig.NODE_ID)
        # 配置服务端
        self.server = GrpcServer(self.config)
        # 配置客户端
        self.client = GrpcClient(self.config)
        # todo ==============暂未实现的GRPC，用fake代替=========================
        self.fake_layer2_node = MockerLayer2nNode()
        for i in range(BHExecutionNodeGlobalConfig.EC_PARAMS_N - 1):
            node_id = BHExecutionNodeGlobalConfig.NODE_ID + i + 1
            self.config.others_address[node_id] = BHExecutionAddress("127.0.0.1",
                                                                     port=self.config.address.get_port() + 1 + i)
            self.fake_other_nodes[node_id] = MockerNode(node_id, self.config.others_address[node_id],
                                                        self.fake_layer2_node)
        # todo ================================================================
        log.write_log("DEBUG", "GrpcEngine load config")

    def start_all(self):
        server_thread = threading.Thread(target=self.server.start_server)
        # 启动服务端线程
        server_thread.start()
        # 启动客户端
        self.client.start_client()

    # todo ===============================暂未实现的GRPC服务====================================
    def send_request(self, node_id, message) -> None:
        """
        模拟发送请求
        """
        # NETWORK
        fake_node: MockerNode = self.fake_other_nodes[node_id]
        fake_node.fake_store_chunk(message)
        log.write_log("DEBUG", "fake request is sent to {}".format(fake_node.ip.get_address()))

    def replicate_encoded_chunks(self, sign, slot, chunks, indices, padding_size, redundancy=False):
        # 发送数据块，redundancy表示是否需要额外冗余存储（纠删码一般不需要，多副本需要）
        # chunks是数据块，indices表示数据块位置索引
        # padding_size是填充0的数量
        # todo 这里是否批量并发，以及是否能提前返回
        if len(chunks) != len(indices):
            raise ValueError("len(chunks) and len(indices) does not match.")
        i = 0
        for node_id in self.fake_other_nodes:
            chunk = chunks[i]
            index = indices[i]
            message = {
                "node_id": BHExecutionNodeGlobalConfig.NODE_ID,
                "sign": sign,
                "slot": slot,
                "index": index,
                "data": chunk,
                "padding": padding_size
            }
            self.send_request(node_id, message)
            i += 1

    def start_test_collect_process(self, node_id, sign, slot):
        # 这里的chunk就是本地的一个，拿出来算作拿到了
        request = self.fake_layer2_node.collect(sign, slot, node_id)
        chunks = []
        indices = []
        for item in request:
            store_node_id, index = item[0], item[1]
            fake_node: MockerNode = self.fake_other_nodes[store_node_id]
            store_chunk = fake_node.load_store_chunk(sign, slot, node_id, index)
            chunks.append(store_chunk["data"])
            indices.append(index)
        return chunks, indices

    def send_store_message(self, node_id, sign, slot, _id, index, padding_size):
        self.fake_layer2_node.update_index(node_id, sign, slot, _id, index)
