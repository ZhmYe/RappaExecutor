from multiprocessing import Process, Queue

from paradigm.channel import Channel
from paradigm.slot import CommitSlotItem


class GrpcRegistry:
    def __init__(self, channel: Channel):
        # 当前节点的id
        self.node_id = None
        # 当前节点的ip和端口
        self.address = None
        # 当前layer2node的ip和端口
        self.layer2_address = None
        # 其他节点的ip和端口
        self.others_address = {}
        # self.slot_hash = {}
        self.slot_buffer = {} # 这里暂时先这样缓存一下 todo @YZM
        self.channel: Channel = channel
    def check_channel_connect(self):
        #todo
        pass