import os
from multiprocessing import Queue, Manager

from config.config import BHExecutionNodeGlobalConfig
from utils.multiprocessing.dict import SuperSharedDict
from paradigm.replicate import ReplicatePackage
from paradigm.slot import CommitSlotItem
from network.Grpc.service.service_pb2 import RecoverSlotChunk
from utils.function.func import get_project_root
from


class Channel:
    def __init__(self, manager: Manager):
        self.manager = manager
        self.to_slot_manager_channel: Queue[CommitSlotItem] = manager.Queue()
        self.to_task_tracker_channel: Queue[CommitSlotItem] = manager.Queue()
        self.to_grpc_replicate_channel: Queue = manager.Queue()
        self.to_grpc_slot_channel: Queue[CommitSlotItem] = manager.Queue()
        self.to_processor_slot_channel: Queue[CommitSlotItem] = manager.Queue()
        self.to_storager_slot_channel: Queue = manager.Queue()
        self.to_receiver_chunk_store_channel: Queue[ReplicatePackage] = manager.Queue()
        self.to_receiver_chunk_load_channel: Queue = manager.Queue()
        self.to_worker_slot_channel: Queue[CommitSlotItem] = manager.Queue()
        self.to_storager_record_channel: Queue = manager.Queue()

        self.slot_buffer_share_dict = manager.dict()

        # 这里加载数据库信息
        self.store_chunks = SuperSharedDict(manager, os.path.join(get_project_root(), "store_chunks.db"), True,
                                            BHExecutionNodeGlobalConfig.IS_RECOVERY)

        self.test_collect_output_channel = manager.Queue()
        self.test_collect_signal_channel = manager.Queue()
        self.test_collect_pass_receiver_channel = manager.Queue()
        self.test_collect_pass_grpc_channel = manager.Queue()
        self.test_replicate_mocker_executor_channel = manager.Queue()

        # self.collect_pass_receiver_channel = manager.Queue()
        # self.collect_pass_grpc_channel = manager.Queue()

        self.collect_connect_channel = manager.Queue()
        self.latest_synth_speed = manager.Value('d', 0.0)

    def update_store_chunk(self, slot_hash, new_store_chunk_item, row_index):
        if not self.store_chunks.get(slot_hash):
            chunks = self.manager.dict()
        else:
            chunks=self.store_chunks[slot_hash]
        chunks[row_index] = new_store_chunk_item
        self.store_chunks[slot_hash] = chunks

    # def create_connect_channel(self, mission):
    #     self.collect_connect_channel[mission] = self.manager.Queue()
    #     return self.collect_connect_channel[mission]
    # def get_connect_channel(self, mission):
    #     if not self.collect_connect_channel[mission]:
    #         raise RuntimeError("not such connection!!!")
    #     return self.collect_connect_channel[mission]
    # def delete_connect_channel(self, mission):
    #     del self.collect_connect_channel[mission]
    def load_store_chunk(self, slot_hash):
        # 这里用于在grpc处得到收集的chunk
        chunks = []
        if not self.store_chunks.get(slot_hash):
            return []
        for row_index, chunk in self.store_chunks[slot_hash].items():
            chunks.append(RecoverSlotChunk(
                hash=chunk.slot_hash,
                row=chunk.row_index,
                col=chunk.col_index,
                chunk=chunk.load()
            ))
            # ===========================截断============================
            """
                HINT: 这里因为现在没有多机测试，为了向Master发送所有的chunk（不然master就只能拿到一个chunk）
                我在这里为了测试写成了在单机上把所有chunk都发过去了，如果是多机场景下，到上面这段代码就结束
                并且简单期间，因为提前知道了命名格式，我就直接read了
            """
            # local_col = chunk.col_index
            # storage_path = chunk.store_path
            # for col in range(BHExecutionNodeGlobalConfig.EC_PARAMS_N):
            #     if col == local_col:
            #         continue
            #     if "-chunk.slot" in storage_path:
            #
            #         # 找到最后一个 '-row-' 和后续的部分
            #         prefix, suffix = storage_path.rsplit('-row-', 1)
            #         parts = suffix.split('-chunk.slot', 1)  # 分割成两个部分
            #         new_path = f"{prefix}-row-{parts[0][:-1] + str(col)}-chunk.slot"
            #         # print(new_path)
            #         try:
            #             with open(new_path, "rb") as f:
            #                 # json.dump(chunk_data, f, ensure_ascii=False, indent=4)
            #                 data = f.read()
            #                 chunks.append(RecoverSlotChunk(
            #                     hash=chunk.slot_hash,
            #                     row=chunk.row_index,
            #                     col=col,
            #                     chunk=data
            #                 ))
            #                 f.close()
            #         except FileNotFoundError:
            #             # 如果是文件不存在的情况，跳过
            #             continue
            #         except Exception as e:
            #             # 其他错误时打印错误信息
            #             # print(f"Error processing file {new_path}: {e}")
            #             raise RuntimeError(f"Error processing file {new_path}: {e}")

        return chunks

    def update_slot_buff(self):
        pass
