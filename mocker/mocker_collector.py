"""
    NOTE: MockerCollector
    这里模拟要把所有存储的内容收回
    最终的代码中不应该有collector，应该是前后端向Master发起collect，然后Master将collect要的slot_hash通过grpc/heartbeat传递给所有节点，然后节点将自己本地的对应部分发给master
    master将结果拼回
"""
import json
import threading
import time
from typing import List

import pandas as pd
from config.config import BHExecutionNodeGlobalConfig, STORE_METHOD_ENUM
from mocker.mocker_executor import MockerExecutor
from network.format import BHExecutionAddress
from paradigm.channel import Channel
from paradigm.replicate import ReplicateChunk, ReplicatePackage
from paradigm.slot import CommitSlotItem
from paradigm.storage import ErasureCodeChunks, ErasureCodeRecoverError
from storage.encoder.rs_decoder import ReedSolomonDecoder
from logger.logger import logWriter as log

class MockerCollector:
    def __init__(self, channel: Channel):
        self.channel = channel
        self.finalized_slots: dict = {} # 这里存slot_hash-> output(dataframe)
        """
        NOTE: 这里暂时还没有实现节点和节点之间的通信
        因此这里先用mocker_executors来暂时代替一下
    """
        self.mocker_executors: List[MockerExecutor] = []
    def process_slot_output(self):
        while True:
            if self.channel.test_collect_output_channel.empty():
                continue
            try:
                item = self.channel.test_collect_output_channel.get(timeout=0.01)
                slot, output, nb_chunks = item[0], item[1], item[2]
                self.finalized_slots[slot.hash] = (output, nb_chunks)
            except Exception as e:
                raise RuntimeError(e)
    def process_finalize_signal(self):
        while True:
            if self.channel.test_collect_signal_channel.empty():
                continue
            try:
                slot: CommitSlotItem = self.channel.test_collect_signal_channel.get(timeout=0.01)
                # 说明slot_hash对应的slot已经finalize了，那么可以测试一下collect，将output发过去
                # 这里就不判断不存在了
                output, nb_chunks = self.finalized_slots[slot.hash]
                self.channel.test_collect_pass_receiver_channel.put((slot, output, nb_chunks))
            except Exception as e:
                raise RuntimeError(e)
    def process_replicate(self):
        while True:
            if self.channel.test_replicate_mocker_executor_channel.empty():
                continue
            try:
                item = self.channel.test_replicate_mocker_executor_channel.get(timeout=0.01)
                node_idx = item[0]
                replicate_package: ReplicatePackage = item[1]
                self.mocker_executors[node_idx].replicate_package(replicate_package=replicate_package)
            except Exception as e:
                raise RuntimeError(e)

    """
        NOTE: 这里是测试collect
    """
    def process_test_collect(self):
        while True:
            if self.channel.test_collect_pass_grpc_channel.empty():
                continue
            try:
                item = self.channel.test_collect_pass_grpc_channel.get(timeout=0.01)
                slot: CommitSlotItem = item[0]
                output, local_chunks = item[1], item[2]
                restored_test_data_merge = pd.DataFrame()
                time.sleep(5)
                if BHExecutionNodeGlobalConfig.STORE_METHOD == STORE_METHOD_ENUM.EC:
                    for row_index in range(len(local_chunks)):
                        # 收集所有的其他块
                        ec_chunks = ErasureCodeChunks(padding_size=slot.replicate_records[row_index].padding_size)
                        ec_chunks.add_chunk(local_chunks[row_index])
                        for mocker_executor in self.mocker_executors:
                            # mocker_executor: MockerExecutor = self.mocker_executors[node_id]
                            chunk = mocker_executor.load(slot.hash, row_index)
                            ec_chunks.add_chunk(chunk)
                        decoder = ReedSolomonDecoder()
                        restored_test_data, error = decoder.decode(ec_chunks)
                        if error != ErasureCodeRecoverError.NONE:
                            raise ValueError("ERROR", "Recover data error: {}".format(error.name))
                        restored_test_data_merge= pd.concat([restored_test_data_merge, restored_test_data], axis=0, ignore_index=True)
                    pd.testing.assert_frame_equal(restored_test_data_merge, output, check_dtype=False, obj="Decoded Dataframe does not match the origin Dataframe")
                if BHExecutionNodeGlobalConfig.STORE_METHOD == STORE_METHOD_ENUM.LOCAL:
                    # 如果是本地，那么本地存的就是全部
                    for row_index in range(len(local_chunks)):
                        decoded_data = b''.join(local_chunks[row_index].chunk)
                        json_str = decoded_data.decode('utf-8')  # 从字节流解码为 JSON 字符串
                            # print(json_str)
                        pd_json = json.loads(json_str.strip())
                        restored_df = pd.DataFrame(pd_json)
                        restored_test_data_merge= pd.concat([restored_test_data_merge, restored_df], axis=0, ignore_index=True)


                log.write_log("DEBUG", "{} recover test success!!!".format(slot.hash))
                log.write_log("DEBUG", "recover result: \n{}".format(restored_test_data_merge))
            except Exception as e:
                raise RuntimeError(e)
    def start(self):
        if BHExecutionNodeGlobalConfig.STORE_METHOD == STORE_METHOD_ENUM.LOCAL:
            log.write_log("DEBUG", "Store Method is local, does not need to start mocker executor...")
            # 如果是本地存储，那么不需要启动，这里为了测试
        else:
            # 如果是纠删码/多副本，目前只有纠删码，那么需要开启mocker receiver模拟下
            for i in range(BHExecutionNodeGlobalConfig.EC_PARAMS_N - 1):
                node_id = BHExecutionNodeGlobalConfig.NODE_ID + i + 1
                address = BHExecutionAddress("127.0.0.1", port=int(BHExecutionNodeGlobalConfig.GRPC_PORT) + 1 + i)
                self.mocker_executors.append(MockerExecutor(node_id, address, self.channel)) # 存储冗余数据块的路径
                self.mocker_executors[i].start()
        # for node_id in self.mocker_executors:
        # mocker_executor = self.mocker_executors[node_id]
        # mocker_executor.start() # 这里方便测试就是在同一个进程里
        process_finalize = threading.Thread(target=self.process_finalize_signal)
        process_slot = threading.Thread(target=self.process_slot_output)
        process_replicate = threading.Thread(target=self.process_replicate)
        process_collect = threading.Thread(target=self.process_test_collect)
        process_finalize.start()
        process_replicate.start()
        process_slot.start()
        process_collect.start()

