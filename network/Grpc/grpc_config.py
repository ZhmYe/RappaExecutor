class GrpcConfig:
    def __init__(self):
        # 当前节点的id
        self.node_id = None
        # 当前节点的ip和端口
        self.address = None
        # 当前layer2node的ip和端口
        self.layer2_address = None
        # 其他节点的ip和端口
        self.others_address = {}
        # 当前任务的队列
        self.pending_task_pool = None
        # 当前任务的完成任务队列
        self.finish_task_pool = None
        # 当前grpc的收到的其他块的队列
        self.receive_chunks_pool = None
