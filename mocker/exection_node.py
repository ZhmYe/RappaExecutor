# 这里用来模拟其它节点
from mocker.layer2node import MockerLayer2nNode
from network.format import BHExecutionNodeAddress, BHExecutionGrpcAddress


class MockerNode:
    # 这里目前测试，其它节点要存文件块
    def __init__(self, _id, ip: BHExecutionGrpcAddress, layer2node: MockerLayer2nNode):
        self.id = _id
        self.files = {}
        self.fake_layer2 = layer2node
        self.ip = ip
    # message = {
    #     "node_id": BHExecutionNodeGlobalConfig.NODE_ID,
    #     "sign": sign,
    #     "slot": slot,
    #     "index": index,
    #     "data": chunk,
    #     "padding": padding_size
    # }
    # 这里模拟接收到消息以后的行为，暂时先不实例化message,也先不算哈希了
    def fake_store_chunk(self, message):
        sign = message["sign"]
        if sign not in self.files:
            self.files[sign] = {}
        slot = message["slot"]
        if slot not in self.files[sign]:
            self.files[sign][slot] = {}
        node_id = message["node_id"]
        if node_id not in self.files[sign][slot]:
            self.files[sign][slot][node_id] = {}
        index = message["index"]
        self.files[sign][slot][node_id][index] = {
            "data": message["data"],
            "padding": message["padding"]
        }
        self.fake_layer2.update_index(self.id, sign ,slot, node_id, message["index"])
    def load_store_chunk(self, sign, slot, node_id, index):
        return self.files[sign][slot][node_id][index]
