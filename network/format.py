# todo 这里定义了节点的地址，目前就是分http和grpc分成了两部分
class BHExecutionNodeAddress:
    def __init__(self, http_ip, http_port, grpc_ip, grpc_port):
        self.http_ip = http_ip
        self.http_port = http_port
        self.grpc_ip = grpc_ip
        self.grpc_port = grpc_port
    def get_http_address(self):
        return {
            "ip": self.http_ip,
            "port": self.http_port
        }
    def get_grpc_address(self):
        return {
            "ip": self.grpc_ip,
            "port": self.grpc_port
        }
class BHExecutionAddress:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
    def get_ip(self):
        return self.ip
    def get_port(self):
        return self.port
    def get_address(self):
        return "{}:{}".format(self.ip, self.port)

# class BHExecutionHttpAddress:
#     def __init__(self, ip, port):
#         self.ip = ip
#         self.port = port
#     def get_ip(self):
#         return self.ip
#     def get_port(self):
#         return self.port