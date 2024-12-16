import grpc
from google.protobuf.json_format import MessageToDict

import network.Grpc.service.services_pb2_grpc as pb2_grpc
import network.Grpc.service.services_pb2 as pb2
from execution.format import PendingTaskPoolItem
from network.Grpc.grpc_config import GrpcConfig
from logger.logger import logWriter as log
from concurrent import futures


#  实现service中节点服务端相关rpc接口
class GrpcServer(pb2_grpc.CoordinatorServicer):
    def __init__(self, grpc_config: GrpcConfig):
        self._grpc_config = grpc_config
        self._core_server = None

    def Heartbeat(self, request, context):
        return super().Heartbeat(request, context)

    def CommitSlot(self, request, context):
        return super().CommitSlot(request, context)

    # 服务端方法，用于处理调度
    def Schedule(self, request, context):
        # 调度不存在或者为0时
        if request.schedule.get(self._grpc_config.node_id, 0) != 0:
            # 节点在其调度内，将任务加入当前任务的队列中
            new_task = PendingTaskPoolItem(
                request.sign, int(request.slot), request.schedule[self._grpc_config.node_id], request.model,
                MessageToDict(request.params)
            )
            log.write_log("DEBUG", f"receive Task {request.sign} Slot {request.slot}")
            self._grpc_config.pending_task_pool.put(new_task)
            return pb2.ScheduleResponse(accept=True, nodeId=self._grpc_config.node_id, sign=request.sign)
        else:
            # 不在调度内，则拒绝
            return pb2.ScheduleResponse(accept=False, nodeId=self._grpc_config.node_id, sign=request.sign,
                                        errorMessage="The Node is not in schedule list.")

    # 开启服务
    def start_server(self):
        self._core_server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        # 将服务添加到服务器
        pb2_grpc.add_CoordinatorServicer_to_server(self, self._core_server)
        self._core_server.add_insecure_port(f"[::]:{self._grpc_config.address.get_port()}")
        log.write_log("DEBUG", f"gRPC server started on port {self._grpc_config.address.get_port()}")
        # 启动grpc
        self._core_server.start()
        self._core_server.wait_for_termination()

    # 关闭服务
    def close_server(self, time=10):
        self._core_server.stop(time)
