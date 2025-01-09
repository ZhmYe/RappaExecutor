import hashlib
import pickle
from enum import Enum, auto

from pandas import DataFrame


class HashFunction(Enum):
    SHA256 = auto()
    POSEIDON = auto()
class Hasher:
    def __init(self, _lambda=1):
        self._lambda = _lambda
    def compute(self, data, hash_function=HashFunction.SHA256)->bytes:
        encoded_data = self._encode(data)
        if hash_function == HashFunction.SHA256:
            return self._compute_sha256(encoded_data)
        if hash_function == HashFunction.POSEIDON:
            return self._compute_poseidon(encoded_data)
    def _encode(self, data):
        if isinstance(data, str):
            return data.encode('utf-8')  # 如果传入的是字符串，先进行编码
        elif isinstance(data, bytes):
            return data
        elif isinstance(data, DataFrame):
            return data.to_csv(index=True).encode('utf-8')
        else:
            return pickle.dumps(data) # 这里dataframe，但后续在zkp里计算的可能是matrix的，因此是否需要判断dataframe然后计算Numpy
        # return data
    def _compute_sha256(self, data)->bytes:
        sha256_hash = hashlib.sha256()
        sha256_hash.update(data)  # 假设data是字符串
        return sha256_hash.digest()
    def _compute_poseidon(self, data)->bytes:
        pass