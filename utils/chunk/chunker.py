# 这里写数据分块逻辑
class Chunker:
    def __init__(self) -> None:
        pass
    def process(self, data, nb_chunk: int)->None:
        # 接收数据，然后将其分块为nb_chunk个数据块，然后用于传到EC里
        # 这里要考虑是否需要对数据进行加密，如果需要的话，那么需要一些密码学手段，比如公私钥等，具体可实现在cryptography下面
        pass