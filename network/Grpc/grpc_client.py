from typing import Optional

import grpc
import threading

from execution.format import PendingTaskPoolItem
from network.Grpc.grpc_config import GrpcConfig
import network.Grpc.service.service_pb2_grpc as pb2_grpc
import network.Grpc.service.service_pb2 as pb2
from logger.logger import logWriter as log


class GrpcClient:
    def __init__(self, grpc_config: GrpcConfig):
        self._grpc_config = grpc_config
        self._stub: Optional[pb2_grpc.CoordinatorStub] = None

    # 客户端方法，提交task slot
    def client_commit_slot(self):
        while True:
            try:
                # 从完成的任务池中获取任务
                if self._grpc_config.finish_task_pool.empty():
                    continue
                finished_task: PendingTaskPoolItem = self._grpc_config.finish_task_pool.get(timeout=1).task
                commit_request = pb2.SlotCommitRequest(
                    nodeId=self._grpc_config.node_id,
                    sign=finished_task.get_sign(),
                    slot=str(finished_task.slot),
                    size=finished_task.get_slot_size()
                )
                commit_response: pb2.SlotCommitResponse = self._stub.CommitSlot(commit_request)
                # 处理结果,这里暂时只打印日志
                log.write_log("DEBUG",
                              f"success upload commit slot{commit_request.slot} of task{commit_request.sign}:[size:{commit_request.size}]")

            except Exception as e:
                log.write_log("ERROR",
                              f"send commit_slot request to {self._grpc_config.layer2_address.get_address()} failed:{e}.", )

    # 开启客户端
    def start_client(self):
        channel = grpc.insecure_channel(self._grpc_config.layer2_address.get_address())
        self._stub = pb2_grpc.CoordinatorStub(channel)
        # 启动所有客户端监视线程
        commit_thread = threading.Thread(target=self.client_commit_slot)
        commit_thread.start()
