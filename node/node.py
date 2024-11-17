# 合成节点实例
# 合成节点需要接收来自BHLayer2的任务
# 考虑使用grpc进行流式传输，简单起见也可以使用http
# 节点每次收到一个任务，就将其放入到任务队列中，每个任务需要有对应的标记
# 每次取出一个任务（先不考虑并行），通过model.loader里的加载方式，根据任务需求加载对应模型，然后进行数据合成
# 将输出格式化返回给BHLayer2，目前的格式化是json也就是dict的形式，如果是grpc还需要修改为proto
from .Task.task import Task
class BHExecutionNode:
    def __init__(self)->None:
        self.grpc_engine = None # grpc
        self.http_engine = None # http
        self.tasks = [] # 所有的任务
        self.task_map = {} # 这里可以用于记录task_sign和task_index的关系
    def process_task(self, params):
        # params: todo
            # sign: 任务标识
            # model: dict
                # model.name: 模型
                # model.params: 模型的一些相关参数
        if params.sign is None:
            pass # todo 这里是不对的
        if params.sign not in self.task_map:
            self.task_map[params.sign] = len(self.tasks)
            task = Task(params)
            self.tasks.append(task)
        else:
            task = self.tasks[self.task_map[params.sign]]
        # 运行task的slot
        task.update_slot(params) # todo 这里params不是想要的

    def checkpoint(self)->None:
        # 如果节点down了，如果还想要尝试恢复历史任务状态（不用担心合成数据，因为已经通过纠删码冗余了）
        # 因为节点状态可能需要作为元数据的一部分，节点需要恢复，因此在这里留一个写checkpoint的接口
        # 可以找到当前节点未完成的所有任务
        # 简单来说就是把当前状态序列化到磁盘里，必要的话可以提供定期清理已有的checkpoint方法
        pass