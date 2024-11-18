import random
import time
from queue import Queue
from typing import NamedTuple, Union

# 仅供测试使用
# 模拟GRPC接收到请求或者假装发起请求

from node.Task.task import  Task
from node.format import TaskPoolItem
from logger.logger import logWriter as log


class FakeGrpcEngine:
    def __init__(self, task_pool: Queue) -> None:

        self.server = None
        self.client = None
        self.task_pool = task_pool
        self.max_task_nb_slot = 10
        self.sign = 0
        self.slot = 0

    def send_request(self, target, message) -> None:
        """
        模拟发送请求
        """
        log.write_log("DEBUG", "fake request is sent...")
    def generate_fake_request(self, tid, sign ,slot)->TaskPoolItem:
        return TaskPoolItem(tid, sign, slot, random.randint(100, 1000), "ctgan")
    def handle_request(self) -> None:
        """
        模拟接收到请求，并将任务放入任务池中。
        :param request: 模拟的请求数据。
        """
        # 将请求转为任务并放入队列

        fake_task = self.generate_fake_request(self.sign, "0x{}".format(self.sign), self.slot)
        self.task_pool.put(fake_task)
        log.write_log("DEBUG", "receive new task slot: \n{}".format(fake_task.format()))
        # print(f"Received request: {request}. Task added: {task}")

    def start_server(self, port=50051) -> None:
        """
        模拟启动 GRPC 服务器，定期向任务队列中添加任务。
        """
        log.write_log("DEBUG", "Fake GRPC server started on port {}".format(port))
        for tid in range(5):
            while self.slot <= self.max_task_nb_slot:
                self.handle_request()
                time.sleep(5)
                self.slot += 1
            self.slot = 0
