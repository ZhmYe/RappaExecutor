import os
from multiprocessing import Process, Queue
from typing import Optional, List

import pandas as pd

from config.config import BHExecutionNodeGlobalConfig
from logger.logger import logWriter as log
from mocker.mocker_executor import MockerExecutor
from network.Grpc.grpc_client import GrpcClient
from network.Grpc.grpc_registry import GrpcRegistry
from network.Grpc.grpc_server import GrpcServer

from network.format import BHExecutionAddress
from paradigm.channel import Channel
from paradigm.replicate import ReplicateChunk, ChunkReplicateRecord
from paradigm.slot import CommitSlotItem
from paradigm.storage import ErasureCodeChunks, ErasureCodeChunk, ErasureCodeRecoverError
from storage.encoder.rs_decoder import ReedSolomonDecoder
from utils.function.func import get_project_root


class GrpcEngine:
    def __init__(self, channel: Channel) -> None:
        # 当前的grpc配置信息
        self.registry = GrpcRegistry(channel=channel)
        # 当前的grpc服务端
        self.server: Optional[GrpcServer] = None
        # 当前的grpc客户端
        self.client: Optional[GrpcClient] = None

        self.redundancy=False # todo @SD 这个加到config里
        # # 所有的通道
        # self.registry.to_grpc_slot_channel= to_grpc_replicate_channel # 这个是那些需要grpc提交的slot
        # self.registry.to_grpc_replicate_channel = to_grpc_replicate_channel # 这些是需要grpc转发的chunk
        # self.registry.to_slot_manager_channel= None # 需要将一些slot传递给slotManager

        """
            NOTE: 这里暂时还没有实现节点和节点之间的通信
            因此这里先用mocker_executors来暂时代替一下
        """
        self.mocker_executors = {}
    def check_channel_connect(self)->bool:
        # todo
        pass

    # 加载配置
    def load_config(self):
        # 导入本机和layer2端地址和端口
        self.registry.address = BHExecutionAddress(BHExecutionNodeGlobalConfig.NODE_IP,
                                                   BHExecutionNodeGlobalConfig.GRPC_PORT)
        self.registry.layer2_address = BHExecutionAddress(BHExecutionNodeGlobalConfig.LAYER2_ADDRESS_IP,
                                                          BHExecutionNodeGlobalConfig.LAYER_ADDRESS_PORT)
        # 导入节点id
        self.registry.node_id = str(BHExecutionNodeGlobalConfig.NODE_ID)
        # 配置服务端
        self.server = GrpcServer(self.registry)
        # 配置客户端
        self.client = GrpcClient(self.registry)
        # self.fake_layer2_node = MockerLayer2nNode()
        # 这里根据N来判断有多少个节点
        for i in range(BHExecutionNodeGlobalConfig.EC_PARAMS_N - 1):
            node_id = BHExecutionNodeGlobalConfig.NODE_ID + i + 1
            self.registry.others_address[node_id] = BHExecutionAddress("127.0.0.1",
                                                                       port=self.registry.address.get_port() + 1 + i)
            self.mocker_executors[node_id] = MockerExecutor(node_id, self.registry.others_address[node_id], self.registry.channel) # 存储冗余数据块的路径
            # self.fake_other_nodes[node_id] = MockerNode(node_id, self.registry.others_address[node_id],
            #                                             self.fake_layer2_node)
        log.write_log("NETWORK", "GrpcEngine load config")

    def start_all(self):
        self.load_config()
        processes = [
            Process(target=self.server.start_server),
            Process(target=self.client.start_client),
            Process(target=self.process_replicate_encoded_chunks)
        ]
        # server_thread = threading.Thread(target=self.server.start_server)
        # 启动服务端线程
        # server_thread.start()
        # 启动客户端
        # self.client.start_client()
        for node_id in self.mocker_executors:
            mocker_executor = self.mocker_executors[node_id]
            mocker_executor.start() # 这里方便测试就是在同一个进程里
            # processes.append(Process(target=mocker_executor.start))
        for process in processes:
            process.start()
        self.process_test_collect()
        for process in processes:
            process.join()





    # todo ===============================暂未实现的GRPC服务====================================
    # todo @XQ 下面的内容要实现到grpc_client中去，主要就是分发数据块和收集数据块
    # 这里要实现的是将冗余数据块分发到对应的节点
    def process_replicate_chunk(self, node_id, replicate_chunk: ReplicateChunk) -> bool:
        """
        模拟发送请求
        """
        mocker_executor: MockerExecutor = self.mocker_executors[node_id]
        # log.write_log("DEBUG", "fake request is sent to {}".format(mocker_executor.ip.get_address()))

        mocker_executor.replicate(replicate_chunk=replicate_chunk) # TODO @XQ 这里要修改成真正的grpc
        return True # 如果分发有错误，要在这里返回

    def process_replicate_encoded_chunks(self):
        # 发送数据块，redundancy表示是否需要额外冗余存储（纠删码一般不需要，多副本需要）
        # chunks是数据块，indices表示数据块位置索引
        # padding_size是填充0的数量
        """
            NOTE: 这里一定要保证所有的块都分发出去了，如果len(chunks) > len(nodes),那么就有若干个nodes存多分份(这里要调整n了说明 todo)
            这里要修改成，一直发送到所有分块都被发出去了每个机器至多持有一个分块 todo@YZM
            需要一些特殊的状态error
        """
        # i = 0
        while True:
            if self.registry.channel.to_grpc_replicate_channel.empty():
                continue
            try:
                # ChunkReplicateRecord, List[ReplicateChunk]
                iter_chunk_replicate_record,  replicate_encoded_chunks = self.registry.channel.to_grpc_replicate_channel.get(timeout=0.01)
                # TODO 这边先简单写一下，其实现在的写法是没法保证上述要求的
                node_id_list: List[MockerExecutor] = [node_id for node_id in self.mocker_executors] # 这里简单起见这么先写
                for (i, chunk) in enumerate(replicate_encoded_chunks):
                    idx = i % len(node_id_list)
                    node_idx = node_id_list[idx]
                    # todo 这里要改成并行
                    if self.process_replicate_chunk(node_idx, chunk):
                        iter_chunk_replicate_record.record_success_replicate(i, self.mocker_executors[node_idx].ip.get_address())
                # 至此,本次转发完成，可以根据record的state()判断是否完成
                # 将转发结果发还给Storager，在storager处，如果record.state()==success那么说明完成了可以将这一slot发给slotmanager，反之要继续
                self.registry.channel.to_storager_record_channel.put(iter_chunk_replicate_record)
            except Exception as e:
                raise RuntimeError(e)
        # node_id_list: List[MockerExecutor] = [node_id for node_id in self.mocker_executors] # 这里简单起见这么先写
        # for (i, chunk) in enumerate(replicate_encoded_chunks):
        #     idx = i % len(node_id_list)
        #     node_idx = node_id_list[idx]
        #     # todo 这里要改成并行
        #     if self.process_replicate_chunk(node_idx, chunk):
        #        iter_chunk_replicate_record.record_success_replicate(i, self.mocker_executors[node_idx].ip.get_address())
        # return iter_chunk_replicate_record





    """
        NOTE: 这里是测试collect
    """
    def process_test_collect(self):
        while True:
            if self.registry.channel.test_collect_pass_grpc_channel.empty():
                continue
            try:
                item = self.registry.channel.test_collect_pass_grpc_channel.get(timeout=0.01)
                slot: CommitSlotItem = item[0]
                output, local_chunks = item[1], item[2]
                restored_test_data_merge = pd.DataFrame()
                for row_index in range(len(local_chunks)):
                    # 收集所有的其他块
                    ec_chunks = ErasureCodeChunks(padding_size=slot.replicate_records[row_index].padding_size)
                    ec_chunks.add_chunk(local_chunks[row_index])
                    for node_id in self.mocker_executors:
                        mocker_executor: MockerExecutor = self.mocker_executors[node_id]
                        chunk = mocker_executor.load(slot.hash, row_index)
                        ec_chunks.add_chunk(chunk)
                    decoder = ReedSolomonDecoder()
                    restored_test_data, error = decoder.decode(ec_chunks)
                    if error != ErasureCodeRecoverError.NONE:
                        raise ValueError("ERROR", "Recover data error: {}".format(error.name))
                    restored_test_data_merge= pd.concat([restored_test_data_merge, restored_test_data], axis=0, ignore_index=True)
                pd.testing.assert_frame_equal(restored_test_data_merge, output, check_dtype=False, obj="Decoded Dataframe does not match the origin Dataframe")
                log.write_log("DEBUG", "{} recover test success!!!".format(slot.hash))
                log.write_log("DEBUG", "recover result: \n{}".format(restored_test_data_merge))
            except Exception as e:
                raise RuntimeError(e)
