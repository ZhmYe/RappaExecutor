import random

from config.config import BHExecutionNodeGlobalConfig
# from network.Grpc.FakeGrpc import FakeGrpcEngine
from logger.logger import logWriter as log

class MockerLayer2nNode:
    def __init__(self):
        self.distribution = {}
        # self.grpc_engine = grpc_engine
        pass
    def update_index(self, _id, sign, slot, node_id, index):
        if sign not in self.distribution:
            self.distribution[sign] = {}
        if slot not in self.distribution[sign]:
            self.distribution[sign][slot] = {}
        if node_id not in self.distribution[sign][slot]:
            self.distribution[sign][slot][node_id] = {}
        self.distribution[sign][slot][node_id][index] = _id # 这里暂时不管重复的事情，代码保证不重复
        log.write_log("DEBUG", "update task {} slot {} chunk {} from node {} store in node {}".format(sign ,slot, index, node_id, _id))
    def collect(self, sign, slot, node_id):
        # 收集task_sign的第i个slot，然后去向所有节点要需要的块,这里暂时假定每个节点就是存了一个块，然后节点数量就是n，一共要k个
        # 也先不管节点是否down了，就随机选择k个节点拿到块
        # 那么这里只需要给出每个node_id的k个随机index
        slot_instance = self.distribution[sign][slot]
        request = []
        # for node_id in slot_instance:
        # request[node_id] = []
        random_k_chunk = random.sample(list(range(BHExecutionNodeGlobalConfig.EC_PARAMS_N)), BHExecutionNodeGlobalConfig.EC_PARAMS_K + 1)
        for index in random_k_chunk:
            if slot_instance[node_id][index] != BHExecutionNodeGlobalConfig.NODE_ID:
                request.append([slot_instance[node_id][index], index])
        return request



