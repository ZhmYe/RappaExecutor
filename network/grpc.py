# 这里写grpc的实现逻辑，下面的框架暂时仅供参考
class GrpcEngine:
    def __init__(self) -> None:
        # 每个节点都有一个grpc server和grpc client
        # grpc server用于接收来自其它节点的数据块（以及可能用于用来接收来自Layer2Node的合成请求，这部分可能在http完成）
        self.server = None
        # grpc client用于向其它节点发送数据块（以及可能用于向Layer2Node提交阶段心跳，这部分可能在http完成）
        self.client = None
    def send_request(self) ->None:
        # 这里写发请求的逻辑，也就是client
        pass
    def handle_request(self) ->None:
        # 这里写接收到请求的逻辑，也就是server,但显然这里需要外面有一个类似listener的东西时刻监听grpc端口，监听到请求时调用该函数
        pass