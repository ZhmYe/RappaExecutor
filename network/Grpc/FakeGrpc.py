import random
import time
from queue import Queue
from mocker.layer2node import MockerLayer2nNode
from mocker.exection_node import MockerNode
from network.format import BHExecutionAddress
# 仅供测试使用
# 模拟GRPC接收到请求或者假装发起请求

from _execution.format import PendingTaskPoolItem
from logger.logger import logWriter as log
from config.config import BHExecutionNodeGlobalConfig

class FakeGrpcEngine:
    def __init__(self, pending_task_pool=Queue(), finish_task_pool=Queue(), receive_chunks_pool=Queue()) -> None:
        self.address = BHExecutionAddress("127.0.0.1", "0")
        self.server = None
        self.client = None
        self.pending_task_pool = pending_task_pool
        self.finish_task_pool = finish_task_pool
        self.receive_chunks_pool = receive_chunks_pool
        self.max_task_nb_slot = 10

        self.sign = random.randint(1, 100)
        self.slot = 0

        self.fake_other_nodes = {}
        self.fake_layer2_node: MockerLayer2nNode = None
    def load_config(self):
        self.address = BHExecutionAddress(BHExecutionNodeGlobalConfig.NODE_IP, BHExecutionNodeGlobalConfig.GRPC_PORT)
        log.write_log("DEBUG", "FakeGrpcEngine load config")
        # 这里就简单的随机生成几个ip和port
        self.fake_layer2_node = MockerLayer2nNode()
        for i in range(BHExecutionNodeGlobalConfig.EC_PARAMS_N - 1):
            # self.ips.append(BHExecutionGrpcAddress("127.0.0.1", port=self.address.get_port() + 1))
            node_id = BHExecutionNodeGlobalConfig.NODE_ID + i + 1
            self.fake_other_nodes[node_id] = MockerNode(node_id, BHExecutionAddress("127.0.0.1", port=self.address.get_port() + 1 + i), self.fake_layer2_node)


    def send_heartbeat(self, message)->None:
        pass
    def send_request(self, node_id, message) -> None:
        """
        模拟发送请求
        """
        # NETWORK
        fake_node:MockerNode = self.fake_other_nodes[node_id]
        fake_node.fake_store_chunk(message)
        log.write_log("DEBUG", "fake request is sent to {}".format(fake_node.ip.get_address()))

    def generate_fake_request(self, sign ,slot)->PendingTaskPoolItem:
        return PendingTaskPoolItem(sign, slot, random.randint(100, 1000), "CTGAN")
    def handle_request(self) -> None:
        """
        模拟接收到请求，并将任务放入任务池中。
        :param request: 模拟的请求数据。
        """
        # 将请求转为任务并放入队列
        # sign = random.randint(1, 100)
        # slot = random.randint(1, 100)
        fake_task = self.generate_fake_request("0x{}".format(self.sign), self.slot)
        self.pending_task_pool.put(fake_task)
        # NETWORK
        log.write_log("DEBUG", "receive new task slot: \n{}".format(fake_task.format()))
        # print(f"Received request: {request}. Task added: {task}")

    def start(self) -> None:
        """
        模拟启动 GRPC 服务器，定期向任务队列中添加任务。
        """
        # 这里正式的可以用NETWORK
        log.write_log("DEBUG", "Grpc Engine Start, Grpc server listened at {}".format(self.address.get_address()))
        for tid in range(5):
            while self.slot <= self.max_task_nb_slot:
                self.handle_request()
                time.sleep(5)
                self.slot += 1
            self.slot = 0


    # 下面的函数仅供模拟

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
        pass




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