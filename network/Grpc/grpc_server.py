from typing import List

import grpc
from google.protobuf.json_format import MessageToDict

import network.Grpc.service.service_pb2_grpc as pb2_grpc
import network.Grpc.service.service_pb2 as pb2
from network.Grpc.grpc_registry import GrpcRegistry
from logger.logger import logWriter as log, logWriter
from concurrent import futures
import utils.system.sys_monitor as sys_monitor
from paradigm.model import CommitSlotModelParams
from paradigm.slot import CommitSlotItem


#  实现service中节点服务端相关rpc接口
class GrpcServer(pb2_grpc.RappaExecutorServicer):
    def __init__(self, registry: GrpcRegistry):
        self._registry = registry
        self._core_server = None

    def Heartbeat(self, request: pb2.HeartbeatRequest, context):
        # TODO 这里暂时这样做,简单实现一下
        votes = []
        status = {}
        logWriter.write_log("NETWORK", f"receive heartbeat.vote for {len(request.commits)} commits.")
        for slot_hash in request.commits:
            votes.append(pb2.Vote(
                hash='12345678',
                nodeId=int(self._registry.node_id),
                commitment=bytes('12345678', 'utf-8'),
                state=True,
                desp='agree everything'
            ))
        # add by zhmye
        for slot_hash in request.justifieds:
            # 判断是否有自己的
            if slot_hash in self._registry.channel.slot_buffer_share_dict:
                # 说明自己的slot通过了投票
                slot: CommitSlotItem = self._registry.channel.slot_buffer_share_dict[slot_hash]
                slot.sign_as_justified()
                self._registry.channel.slot_buffer_share_dict[slot_hash] = slot
                self._registry.channel.to_slot_manager_channel.put(slot)
        for slot_hash in request.finalizes:
            # 判断是否有自己的
            if slot_hash in self._registry.channel.slot_buffer_share_dict:
                # 说明自己的slot通过了投票
                slot: CommitSlotItem = self._registry.channel.slot_buffer_share_dict[slot_hash]
                slot.sign_as_finalized()
                self._registry.channel.to_slot_manager_channel.put(slot)
                # 删除buffer
                del self._registry.channel.slot_buffer_share_dict[slot_hash]
                # self._registry.slot_buffer[slot_hash] = slot
        # 简单获取一个内存占用
        total_memory, used_memory, memory_usage = sys_monitor.get_memory_info()
        status['memory_usage'] = str(memory_usage)
        status['total_memory'] = str(total_memory)
        status['used_memory'] = str(used_memory)

        return pb2.HeartbeatResponse(
            nodeId=int(self._registry.node_id),
            nodeStatus=status,
            votes=votes,
        )

    # 服务端方法，用于处理调度
    def Schedule(self, request: pb2.ScheduleRequest, context):
        # print(request.nodeID, self._registry.node_id, request.nodeID == self._registry.node_id)
        if int(request.nodeID) == int(self._registry.node_id):
        #
        # if request.schedule.get(self._registry.node_id, 0) != 0:
            # 节点在其调度内，将任务加入当前任务的队列中
            # new_task = PendingTaskPoolItem(
            #     request.sign, int(request.slot), request.schedule[self._registry.node_id], request.model,
            #     MessageToDict(request.params)
            # )
            # modify by zhmye
            new_slot = CommitSlotItem(
                request.sign,
                request.slot,
                request.size,
                CommitSlotModelParams(
                    request.model,
                    MessageToDict(request.params)
                )

            )
            new_slot.set_hash(request.hash)
            log.write_log("NETWORK", f"receive Task {request.sign} Slot {request.slot} Schedule {request.hash}")
            self._registry.channel.to_slot_manager_channel.put(new_slot)
            return pb2.ScheduleResponse(accept=True, nodeId=self._registry.node_id, sign=request.sign)
        else:
            # 不在调度内，则拒绝
            return pb2.ScheduleResponse(accept=False, nodeId=self._registry.node_id, sign=request.sign,
                                        errorMessage="The Node is not in schedule list.")


    # 服务端方法，用于处理收集请求
    def Collect(self, request: pb2.RecoverRequest, context):
        # 这里要将请求转给receiver，然后读出来
        slot_hashs = request.hashs
        # connect = self._registry.channel.create_connect_channel(str(request.mission)) # 创建传输专用的通道
        chunks = []
        # print(slot_hashs, request.mission)
        # self._registry.channel.collect_pass_receiver_channel.put((list(slot_hashs), str(request.mission))) # 传递hash和通道给receiver
        # while True:
        #     if self._registry.channel.collect_connect_channel.empty():
        #         continue
        #     try:
        #         chunks = self._registry.channel.collect_connect_channel.get(timeout=0.01)
        #         print(chunks)
        #         if chunks is not None:
        #             break
        #     except Exception as e:
        #         raise RuntimeError(e)
        # print(chunks)
        for slot_hash in slot_hashs:
            chunks.extend(self._registry.channel.load_store_chunk(slot_hash=slot_hash))
        # self._registry.channel.delete_connect_channel(str(request.mission))
        return pb2.RecoverResponse(chunks=chunks)
        # for slot_hash in slot_hashs:
            # print(self._registry)
            # chunks.extend(self._registry.channel.load_store_chunk(slot_hash=slot_hash))
    # 开启服务
    def start_server(self):
        self._core_server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        # 将服务添加到服务器
        pb2_grpc.add_RappaExecutorServicer_to_server(self, self._core_server)
        self._core_server.add_insecure_port(f"[::]:{self._registry.address.get_port()}")
        # 启动grpc
        self._core_server.start()
        log.write_log("NETWORK", f"gRPC server started on port {self._registry.address.get_port()}")
        self._core_server.wait_for_termination()

    # 关闭服务
    def close_server(self, time=10):
        self._core_server.stop(time)
