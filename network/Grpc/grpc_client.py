import json
import time
from typing import Optional

import grpc
import threading

from grpc import Channel
from network.Grpc.grpc_registry import GrpcRegistry
import network.Grpc.service.service_pb2_grpc as pb2_grpc
import network.Grpc.service.service_pb2 as pb2
from logger.logger import logWriter as log
from paradigm.slot import CommitSlotItem


class GrpcClient:
    def __init__(self, registry: GrpcRegistry):
        self._registry = registry
        # 这里配置grpc客户端策略
        self._client_config = json.dumps({
            "methodConfig": [{
                "name": [
                    {
                        "service": "service.Coordinator",
                        "method": "CommitSlot"
                    }
                ],
                "retryPolicy": {
                    "maxAttempts": 5,
                    "initialBackoff": "0.1s",
                    "maxBackoff": "2s",
                    "backoffMultiplier": 1.6,
                    "retryableStatusCodes": ["UNAVAILABLE", "DEADLINE_EXCEEDED"]
                }
            }]
        })
        self._channel: Optional[Channel] = None

    # 客户端方法，提交task slot
    def client_commit_slot(self):
        while True:
            if self._registry.finish_task_pool.empty():
                continue
            try:
                # 从完成的任务池中获取任务
                commit_slot: CommitSlotItem = self._registry.finish_task_pool.get(timeout=1)
                if not commit_slot.is_undetermined():
                    raise ValueError("Commit Slot must be UNDETERMINED!!!")


                commit_request = pb2.SlotCommitRequest(
                    nodeId=int(self._registry.node_id),
                    sign=commit_slot.sign,
                    slot=commit_slot.slot,
                    size=commit_slot.size,
                    commitment=bytes(commit_slot.commitment, 'utf-8')
                )
                # 发送grpc请求
                stub = pb2_grpc.CoordinatorStub(self._channel)
                commit_response: pb2.SlotCommitResponse = stub.CommitSlot(commit_request, timeout=5,
                                                                          wait_for_ready=True)
                # 对提交结果进行处理
                self._commit_result_process(commit_slot, commit_response)
                # 处理结果,这里暂时只打印日志
                log.write_log("DEBUG",
                              f"successfully upload commit slot{commit_request.slot} of task{commit_request.sign}:[size:{commit_request.size}]")

            except Exception as e:
                log.write_log("ERROR", f"faild to commit slot because of {e}")

    # TODO 这里处理layer返回commit的结果
    def _commit_result_process(self, slot: CommitSlotItem, response: pb2.SlotCommitResponse):
        # 这里response应该暂时是不涉及invalid的
        slot_hash = response.hash
        slot.set_hash(slot_hash)
        self._registry.slot_buffer[slot_hash] = slot # todo 暂时先这样写
        # self._registry.slot_hash[slot_hash] = True
        self._registry.slot_channel.put(slot) # 传递到slot_channel
        pass

    # 创建 channel
    def _create_channel(self):
        # 配置重试机制和其它参数,创建 gRPC Channel
        channel = grpc.insecure_channel(self._registry.layer2_address.get_address(), options=[
            ('grpc.service_config', self._client_config)
        ])
        # 订阅状态监测
        channel.subscribe(self._on_state_change, try_to_connect=True)
        return channel

    # 用于监听channel的状态变化
    def _on_state_change(self, state):
        # 这里先实现一个状态监测，通道没有接通
        # TODO: 这里是3.10的写法
        # match state:
        #     case grpc.ChannelConnectivity.TRANSIENT_FAILURE:
        #         log.write_log("ERROR", f"{self._registry.layer2_address.get_address()} can not ping,try again!")
        if state == grpc.ChannelConnectivity.TRANSIENT_FAILURE:
            log.write_log("WARNING", f"{self._registry.layer2_address.get_address()} can not ping,try again!")

    # 开启客户端
    def start_client(self):
        self._channel = self._create_channel()
        # 启动所有客户端监视线程
        commit_thread = threading.Thread(target=self.client_commit_slot)
        commit_thread.start()
