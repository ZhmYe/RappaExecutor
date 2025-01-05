# 这里写merkle_root，这是最常见的向量承诺
from typing import List

from utils.cryptography.hash.hasher import Hasher, HashFunction


class MerkleTree:
    def __init__(self, data: List[bytes], hasher: Hasher)->None:
        self.leaves: List[bytes] = data
        self.hasher = hasher
    # TODO 这里的返回值一定是str? @YZM
    def compute_root(self, hf=HashFunction.SHA256)->str:
        # 计算merkle_root
        if len(self.leaves) == 1:
            # 如果只有一个值，那么直接返回即可
            return self.hasher.compute(data=self.leaves[0], hash_function=hf)
        data = [self.hasher.compute(data=leaf, hash_function=hf) for leaf in self.leaves]
        while len(data) > 1:
            if len(data) % 2 == 1:
                data.append(data[-1])
            tmp = []
            for i in range(0, len(data), 2):
                tmp.append(self.hasher.compute(data=data[i] + data[i+1], hash_function=hf))
            # if len(data) % 2 == 1:
            #     tmp.append(self.hasher.compute(data=data[-1] + data[-1], hash_function=hf))
            data = tmp
        return data[0]

