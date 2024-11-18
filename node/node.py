# 合成节点实例
# 合成节点需要接收来自BHLayer2的任务
# 考虑使用grpc进行流式传输，简单起见也可以使用http
# 节点每次收到一个任务，就将其放入到任务队列中，每个任务需要有对应的标记
# 每次取出一个任务（先不考虑并行），通过model.loader里的加载方式，根据任务需求加载对应模型，然后进行数据合成
# 将输出格式化返回给BHLayer2，目前的格式化是json也就是dict的形式，如果是grpc还需要修改为proto
import threading
from queue import Queue
from logger.logger import logWriter as log
from network.Grpc.FakeGrpc import FakeGrpcEngine
from network.Grpc.grpc import GrpcEngine

from .Task.task import Task
from .format import TaskPoolItem
from config.config import BHExecutionNodeGlobalConfig

class BHExecutionNode:
    def __init__(self)->None:
        self.id = -1 # 节点的唯一标识
        self.task_pool = Queue()
        self.debug = BHExecutionNodeGlobalConfig.get_debug()  # 从全局配置获取调试模式
        self.grpc_engine = (
            FakeGrpcEngine(self.task_pool) if self.debug else GrpcEngine(self.task_pool)
        )
        self.http_engine = None # http
        self.tasks = [] # 所有的任务
        self.task_map = {} # 这里可以用于记录task_sign和task_index的关系
    def load_config(self, config_name):
        # 这里用来加载节点的配置，比如grpc address等
        log.write_log("INFO", "load config from {}".format(config_name))
        self.info()
        pass
    def start(self):
        # 节点运行逻辑

        # Version_0.1 首先我们先不考虑来自Layer2Node的内容，先把格式定好
        """
       Start the node to process tasks from the task pool.
       """
        # Start gRPC server in a separate thread
        # start前要先把load_config运行了
        grpc_thread = threading.Thread(target=self.grpc_engine.start_server)
        grpc_thread.start()

        # Start processing tasks
        log.write_log("INFO", "BHExecution Node Start...")
        while True:
            try:
                # Get a task from the task pool (blocking)
                if self.task_pool.empty():
                    continue
                task_data = self.task_pool.get(timeout=1)  # Wait for a task
                self.process_task(task_data)
            except Exception as e:
                raise RuntimeError(e)

        pass
    def process_task(self, params: TaskPoolItem):
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
        task.update_slot(params.slot) # todo,这里的params()是slot内部的参数
        log.write_log("TRACK", "process Task Slot finished: \n {}".format(params.format()))




    def info(self):
        # 这里是节点的配置信息输出，暂时可以不管
        pass


    def checkpoint(self)->None:
        # 如果节点down了，如果还想要尝试恢复历史任务状态（不用担心合成数据，因为已经通过纠删码冗余了）
        # 因为节点状态可能需要作为元数据的一部分，节点需要恢复，因此在这里留一个写checkpoint的接口
        # 可以找到当前节点未完成的所有任务
        # 简单来说就是把当前状态序列化到磁盘里，必要的话可以提供定期清理已有的checkpoint方法
        pass