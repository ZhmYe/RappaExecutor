import random
import time
from queue import Queue
from typing import NamedTuple, Union
from config.config import BHExecutionNodeGlobalConfig
from network.format import BHExecutionGrpcAddress
# 仅供测试使用
# 模拟GRPC接收到请求或者假装发起请求

from node.Task.task import  Task
from node.format import PendingTaskPoolItem
from logger.logger import logWriter as log
from config.config import BHExecutionNodeGlobalConfig

class FakeGrpcEngine:
    def __init__(self, pending_task_pool=Queue(), finish_task_pool=Queue(), receive_chunks_pool=Queue()) -> None:
        self.address = BHExecutionGrpcAddress("127.0.0.1", "0")
        self.server = None
        self.client = None
        self.pending_task_pool = pending_task_pool
        self.finish_task_pool = finish_task_pool
        self.receive_chunks_pool = receive_chunks_pool
        self.max_task_nb_slot = 10
        self.ips = [] # 这里要存储所有其它节点的address，表示为BHExecutionNodeGrpcAddress
        self.layer2node_ip = "" # 这里存储layer2node的ip


        self.sign = random.randint(1, 100)
        self.slot = 0
    def load_config(self):
        self.address = BHExecutionGrpcAddress(BHExecutionNodeGlobalConfig.NODE_IP, BHExecutionNodeGlobalConfig.GRPC_PORT)
        log.write_log("DEBUG", "FakeGrpcEngine load config")
        # 这里就简单的随机生成几个ip和port
        for i in range(10):
            # 10台机器，每台端口累加，ip本地
            self.ips.append(BHExecutionGrpcAddress("127.0.0.1", port=self.address.get_port() + 1))
    def send_heartbeat(self, message)->None:
        pass
    def send_request(self, target: BHExecutionGrpcAddress, message) -> None:
        """
        模拟发送请求
        """
        # NETWORK
        log.write_log("DEBUG", "fake request is sent to {}".format(target.get_address()))
    def generate_fake_request(self, sign ,slot)->PendingTaskPoolItem:
        return PendingTaskPoolItem(sign, slot, random.randint(100, 1000), "ctgan")
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

    def start_server(self, port=50051) -> None:
        """
        模拟启动 GRPC 服务器，定期向任务队列中添加任务。
        """
        # 这里正式的可以用NETWORK
        log.write_log("DEBUG", "Fake GRPC server started on port {}".format(port))
        for tid in range(5):
            while self.slot <= self.max_task_nb_slot:
                self.handle_request()
                time.sleep(5)
                self.slot += 1
            self.slot = 0



    def replicate_encoded_chunks(self, sign, slot, chunks, indices, padding_size, redundancy=False):
        # 发送数据块，redundancy表示是否需要额外冗余存储（纠删码一般不需要，多副本需要）
        # chunks是数据块，indices表示数据块位置索引
        # padding_size是填充0的数量
        # todo 这里是否批量并发，以及是否能提前返回
        if len(chunks) != len(indices):
            raise ValueError("len(chunks) and len(indices) does not match.")
        for i in range(len(chunks)):
            chunk = chunks[i]
            index = indices[i]
            message = {
                "node_id": BHExecutionNodeGlobalConfig.NODE_ID,
                "sign": sign,
                "slot": slot,
                "index": index,
                "data": chunk,
            }
            self.send_request(self.ips[index], message)
        pass


