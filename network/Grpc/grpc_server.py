import grpc
from google.protobuf.json_format import MessageToDict

import network.Grpc.service.service_pb2_grpc as pb2_grpc
import network.Grpc.service.service_pb2 as pb2
from execution.format import PendingTaskPoolItem
from network.Grpc.grpc_registry import GrpcRegistry
from logger.logger import logWriter as log
from concurrent import futures
import utils.system.sys_monitor as sys_monitor


#  实现service中节点服务端相关rpc接口
class GrpcServer(pb2_grpc.NodeExecutorServicer):
    def __init__(self, registry: GrpcRegistry):
        self._registry = registry
        self._core_server = None

    def Heartbeat(self, request: pb2.HeartbeatRequest, context):
        # TODO 这里暂时这样做
        votes = []
        status = {}
        for slot in request.commits:
            votes.append(pb2.Vote(
                slot=slot,
                nodeId=request.nodeId,
                status=True,
                desp='agree everything'
            ))

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
        # 调度不存在或者为0时
        if request.schedule.get(self._registry.node_id, 0) != 0:
            # 节点在其调度内，将任务加入当前任务的队列中
            new_task = PendingTaskPoolItem(
                request.sign, int(request.slot), request.schedule[self._registry.node_id], request.model,
                MessageToDict(request.params)
            )
            log.write_log("DEBUG", f"receive Task {request.sign} Slot {request.slot}")
            self._registry.pending_task_pool.put(new_task)
            return pb2.ScheduleResponse(accept=True, nodeId=self._registry.node_id, sign=request.sign)
        else:
            # 不在调度内，则拒绝
            return pb2.ScheduleResponse(accept=False, nodeId=self._registry.node_id, sign=request.sign,
                                        errorMessage="The Node is not in schedule list.")

    # 开启服务
    def start_server(self):
        self._core_server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        # 将服务添加到服务器
        pb2_grpc.add_NodeExecutorServicer_to_server(self, self._core_server)
        self._core_server.add_insecure_port(f"[::]:{self._registry.address.get_port()}")
        # 启动grpc
        self._core_server.start()
        log.write_log("DEBUG", f"gRPC server started on port {self._registry.address.get_port()}")
        self._core_server.wait_for_termination()

    # 关闭服务
    def close_server(self, time=10):
        self._core_server.stop(time)
