# 合成节点实例
# 合成节点需要接收来自BHLayer2的任务
# 考虑使用grpc进行流式传输，简单起见也可以使用http
# 节点每次收到一个任务，就将其放入到任务队列中，每个任务需要有对应的标记
# 每次取出一个任务（先不考虑并行），通过model.loader里的加载方式，根据任务需求加载对应模型，然后进行数据合成
# 将输出格式化返回给BHLayer2，目前的格式化是json也就是dict的形式，如果是grpc还需要修改为proto
import threading
from queue import Queue
from logger.logger import logWriter as log
from model.format import ModelFormatOutput
from network.Grpc.FakeGrpc import FakeGrpcEngine
from storage.storager import Storager
# from network.Grpc.grpc import GrpcEngine

from .Task.task import Task
from .format import PackedTaskOutput, FinishTaskPoolItem, PendingTaskPoolItem
from config.config import BHExecutionNodeGlobalConfig

class BHExecutionNode:
    def __init__(self, pending_task_pool=Queue(), finish_task_pool=Queue())->None:
        self.id = -1 # 节点的唯一标识

        self.pending_task_pool = pending_task_pool # 等待处理的任务slot
        self.finish_task_pool = finish_task_pool # 已经完成的任务slot，用于grpc发送心跳
        self.grpc_engine = None
        # self.http_engine = None # http
        self.tasks = [] # 所有的任务
        self.task_map = {} # 这里可以用于记录task_sign和task_index的关系
        self.storager = None

    def load_config(self):
        # todo
        log.write_log("INFO", "BHExecutionNode load config...")
        self.id = BHExecutionNodeGlobalConfig.NODE_ID


    def set_grpc_engine(self, grpc_engine):
        self.grpc_engine = grpc_engine

    def set_storager(self, storager: Storager):
        self.storager = storager

    def start(self):
        # 节点运行逻辑

        # Version_0.1 首先我们先不考虑来自Layer2Node的内容，先把格式定好
        """
       Start the node to process tasks from the task pool.
       """
        # Start gRPC server in a separate thread
        # # start前要先把load_config运行了
        # grpc_thread = threading.Thread(target=self.grpc_engine.start_server)
        # grpc_thread.start()

        # Start processing tasks
        log.write_log("INFO", "BHExecution Node Start...")
        while True:
            try:
                # Get a task from the task pool (blocking)
                if self.pending_task_pool.empty():
                    continue
                task_data: PendingTaskPoolItem = self.pending_task_pool.get(timeout=1)  # Wait for a task
                output = self.process_task(task_data) # 这里得到了一个输出，我们要将它放到grpc client里，以及要把输出放到storage里
                # 接下来要做的事情
                # todo 这里其实还需要机器在发送心跳前down了，那么数据可恢复但是平台不知道，可以在节点的心跳里加入收到了哪些数据块？
                # 1. 将output用纠删码进行冗余块生成，并计算output的哈希值（用于完整性验证）
                # 2. 将output用纠删码进行冗余块生成，然后分发到其它节点，当有超过k个节点反应说自己已经收到并存储了冗余块的时候（可以保证容错）
                # 3. 向Layer2Node发送心跳，说明自己已经做完了
                # 处理输出，得到数据块并分发
                commitment = self.storager.handle_model_output(PackedTaskOutput(task_data.get_sign(), task_data.slot, output))
                # 数据块已经备份，可恢复,将当前slot放入finish
                self.finish_task_pool.put(FinishTaskPoolItem(commitment, task_data))
            except Exception as e:
                raise RuntimeError(e)

        pass
    def process_task(self, params: PendingTaskPoolItem)->ModelFormatOutput:
        if params.sign is None:
            raise ValueError("TaskPoolItem.sign should not be None")
        # 取出对应的task，这样写可能不太好，先这样
        # 考虑到会有并发的请求，所以会出现上一个任务还没做完下一个任务就开始了
        # 这里先不考虑并发运行task todo
        if params.sign not in self.task_map:
            self.task_map[params.sign] = len(self.tasks)
            task = Task(params)
            self.tasks.append(task)
        else:
            task = self.tasks[self.task_map[params.sign]]
        # 运行task的slot
        output = task.update_slot(params.slot) # todo,这里的params()是slot内部的参数
        log.write_log("EXECUTION", "process Task {} Slot {}finished".format(params.sign, params.slot.id))
        return output




    def checkpoint(self)->None:
        # 如果节点down了，如果还想要尝试恢复历史任务状态（不用担心合成数据，因为已经通过纠删码冗余了）
        # 因为节点状态可能需要作为元数据的一部分，节点需要恢复，因此在这里留一个写checkpoint的接口
        # 可以找到当前节点未完成的所有任务
        # 简单来说就是把当前状态序列化到磁盘里，必要的话可以提供定期清理已有的checkpoint方法
        pass