from dataclasses import fields

import grpc
from google.protobuf.json_format import MessageToDict

# grpcio-tools要下载 1.43.0版本，高版本会报错，没有services这个属性

import network.Grpc.service.services_pb2_grpc as pb2_grpc
import network.Grpc.service.services_pb2 as pb2
from concurrent import futures
from queue import Queue
from mocker.exection_node import MockerNode
from config.config import BHExecutionNodeGlobalConfig
from execution.format import PendingTaskPoolItem
from logger.logger import logWriter as log
from mocker.layer2node import MockerLayer2nNode

from network.format import BHExecutionGrpcAddress


class GrpcEngine:
    #  实现service中节点服务端相关rpc接口
    class CoordinatorService(pb2_grpc.CoordinatorServicer):
        def __init__(self, grpc_engine):
            self._grpc_engine = grpc_engine

        def Heartbeat(self, request, context):
            return super().Heartbeat(request, context)

        def EpochVote(self, request, context):
            return super().EpochVote(request, context)

        def CommitSlot(self, request, context):
            return super().CommitSlot(request, context)

        def Schedule(self, request, context):
            return self._grpc_engine.server_handle_schedule(request, context)

    def __init__(self, pending_task_pool=Queue(), finish_task_pool=Queue(), receive_chunks_pool=Queue()) -> None:
        # 当前节点的id
        self.node_id = None
        # 当前节点的ip和端口
        self.address = None
        # 当前layer2node的ip和端口
        self.layer2_address = None
        # 当前的grpc服务
        self.service = None
        # 当前的grpc服务端
        self.server = None
        # 当前grpc的客户端
        self.client = None
        # 当前任务的队列
        self.pending_task_pool = pending_task_pool
        # 当前任务的完成任务队列
        self.finish_task_pool = finish_task_pool
        # 当前grpc的收到的其他块的队列
        self.receive_chunks_pool = receive_chunks_pool

        # todo ==============暂未实现部分，使用fake替代==========================
        self.fake_layer2_node = None
        self.fake_other_nodes = {}

    def load_config(self):
        # 导入本机和layer2端地址和端口
        self.address = BHExecutionGrpcAddress(BHExecutionNodeGlobalConfig.NODE_IP,
                                              BHExecutionNodeGlobalConfig.GRPC_PORT)
        self.layer2_address = BHExecutionGrpcAddress(BHExecutionNodeGlobalConfig.LAYER2_ADDRESS_IP,
                                                     BHExecutionNodeGlobalConfig.LAYER_ADDRESS_PORT)

        # todo ==============暂未实现的GRPC，用fake代替=========================
        self.fake_layer2_node = MockerLayer2nNode()
        for i in range(BHExecutionNodeGlobalConfig.EC_PARAMS_N - 1):
            node_id = BHExecutionNodeGlobalConfig.NODE_ID + i + 1
            self.fake_other_nodes[node_id] = MockerNode(node_id, BHExecutionGrpcAddress("127.0.0.1",
                                                                                        port=self.address.get_port() + 1 + i),
                                                        self.fake_layer2_node)
        # ================================================================
        # 导入节点id
        self.node_id = BHExecutionNodeGlobalConfig.NODE_ID
        log.write_log("DEBUG", "GrpcEngine load config")

    # 服务端方法，用于处理调度
    def server_handle_schedule(self, request, context) -> pb2.ScheduleResponse:
        if str(self.node_id) in request.schedule:
            # 节点在其调度内，将任务加入当前任务的队列中
            new_task = PendingTaskPoolItem(
                request.sign, int(request.slot), int(request.schedule[str(self.node_id)]), request.model,
                MessageToDict(request.params)
            )
            log.write_log("DEBUG", f"receive Task {request.sign} Slot {request.slot}")
            self.pending_task_pool.put(new_task)
            return pb2.ScheduleResponse(accept=True, nodeId=str(self.node_id), sign=request.sign)
        else:
            # 不在调度内，则拒绝
            return pb2.ScheduleResponse(accept=False, nodeId=str(self.node_id), sign=request.sign,
                                        errorMessage="The Node is not in schedule list.")

    def start_server(self):
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        self.service = self.CoordinatorService(self)
        # 将服务添加到服务器
        pb2_grpc.add_CoordinatorServicer_to_server(self.service, self.server)
        log.write_log("DEBUG", f"gRPC server started on port {self.address.get_port()}")
        self.server.add_insecure_port(f"[::]:{self.address.get_port()}")
        # 启动grpc
        self.server.start()
        self.server.wait_for_termination()

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
