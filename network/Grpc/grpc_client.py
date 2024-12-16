from network.Grpc.grpc_config import GrpcConfig


class GrpcClient:
    def __init__(self, grpc_config: GrpcConfig):
        self._grpc_config = grpc_config