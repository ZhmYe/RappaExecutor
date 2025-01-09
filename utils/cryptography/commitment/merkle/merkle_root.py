from abc import ABC, abstractmethod
from typing import List, Any

from utils.cryptography.hash.hasher import Hasher, HashFunction


class MerkleTree:
    def __init__(self, hf=HashFunction.SHA256) -> None:
        self.tree: List[List[bytes]] = []

    def compute_root(self, data: List[Any], hf=HashFunction.SHA256) -> bytes:
        data_hash = []
        for leaf in data:
            hasher = Hasher()
            data_hash.append(hasher.compute(data=leaf, hash_function=hf))
        self.tree.append(data_hash)

        while len(data_hash) > 1:
            if len(data_hash) % 2 == 1:
                data_hash.append(data_hash[-1])
            tmp = []
            for i in range(0, len(data_hash), 2):
                hasher = Hasher()
                tmp.append(hasher.compute(data=data_hash[i] + data_hash[i + 1], hash_function=hf))
            data_hash = tmp
            self.tree.append(data_hash)
        return data_hash[0]

    def get_proof(self, index: int) -> List[tuple]:
        proof = []
        level = 0
        while len(self.tree[level]) > 1:
            pair_index = index ^ 1
            if pair_index >= len(self.tree[level]):
                pair_index = index
            proof.append((self.tree[level][pair_index], index % 2 == 0))
            level += 1
            index //= 2
        return proof


class MerkleProof:
    def __init__(self, commitment: Any, proof: List[tuple], index: int) -> None:
        self.commitment = commitment
        self.proof = proof
        self.index = index

    def verify(self, data: Any, hf=HashFunction.SHA256) -> bool:
        hasher = Hasher()
        current_hash = hasher.compute(data=data, hash_function=hf)
        for proof_node, is_left in self.proof:
            if is_left:
                current_hash = hasher.compute(data=current_hash + proof_node, hash_function=hf)
            else:
                current_hash = hasher.compute(data=proof_node + current_hash, hash_function=hf)
        return current_hash == self.commitment


class MerkleCommitment:
    def __init__(self, hf=HashFunction.SHA256) -> None:
        # self.hasher = hasher
        self.merkle_tree: MerkleTree = None
        self.commitment = None
        self.hash_function = hf

    def commit(self, vec: List[Any]):
        """
        提交阶段构建 Merkle 树
        """
        # 数据转换成字节列表
        # for item in vec:
        #     print(item)
        self.merkle_tree = MerkleTree(hf=self.hash_function)
        self.commitment = self.merkle_tree.compute_root(vec)
        # for data in vec:
        #     hasher = Hasher()
        #     print(hasher.compute(data))

    def open(self, data: Any) -> MerkleProof:
        """
        打开某一数据并生成 Merkle 证明
        """
        # 确保哈希逻辑一致
        hasher = Hasher()
        data_hash = hasher.compute(data=data, hash_function=self.hash_function)
        index = None
        for i, leaf in enumerate(self.merkle_tree.tree[0]):
            if leaf == data_hash:
                index = i
                break
        if index is None:
            raise ValueError("Data not found in Merkle tree")

        proof = self.merkle_tree.get_proof(index)
        return MerkleProof(self.commitment, proof, index)

    @staticmethod
    def verify(proof: MerkleProof, data: Any) -> bool:
        """
        静态方法验证 Merkle 证明
        """
        return proof.verify(data)
