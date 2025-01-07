from abc import ABC, abstractmethod
from typing import List, Any

from utils.cryptography.hash.hasher import Hasher, HashFunction


class MerkleTree:
    def __init__(self, data: List[Any], hasher: Hasher) -> None:
        self.leaves: List[Any] = data  # 数据的叶节点
        self.hasher = hasher
        self.tree: List[List[bytes]] = []  # 用于存储树的所有层级

    def compute_root(self, hf=HashFunction.SHA256) -> bytes:
        """
        计算 Merkle 树的根
        """
        if len(self.leaves) == 1:
            # 如果只有一个值，直接返回叶节点的哈希
            return self.hasher.compute(data=self.leaves[0], hash_function=hf)

        data = [self.hasher.compute(data=leaf, hash_function=hf) for leaf in self.leaves]
        self.tree.append(data)

        # 构建 Merkle 树
        while len(data) > 1:
            if len(data) % 2 == 1:
                data.append(data[-1])  # 如果是奇数个叶子节点，复制最后一个节点

            tmp = []
            for i in range(0, len(data), 2):
                tmp.append(self.hasher.compute(data=data[i] + data[i+1], hash_function=hf))
            data = tmp
            self.tree.append(data)

        return data[0]

    def get_proof(self, index: int) -> List[bytes]:
        """
        获取某个叶节点的 Merkle 证明
        """
        proof = []
        # 从底层到上层构建证明路径
        level = 0
        while len(self.tree[level]) > 1:
            pair_index = index ^ 1  # 获取与当前节点相邻的节点的索引
            if pair_index < len(self.tree[level]):
                proof.append(self.tree[level][pair_index])
            level += 1
            index //= 2  # 上层的索引
        return proof


class MerkleProof:
    def __init__(self, commitment: Any, proof: List[bytes], index: int) -> None:
        self.commitment = commitment
        self.proof = proof
        self.index = index

    def verify(self, data: Any, hf=HashFunction.SHA256) -> bool:
        """
        使用 Merkle 证明来验证数据是否在 Merkle 树中
        """
        # 将数据和证明结合，逐层计算 hash
        current_hash = self.commitment.hasher.compute(data=data, hash_function=hf)
        for proof_node in self.proof:
            # 每次计算时都和相邻的节点合并，并计算哈希
            current_hash = self.commitment.hasher.compute(data=current_hash + proof_node, hash_function=hf)
        return current_hash == self.commitment.merkle_tree.compute_root(hf)


class MerkleCommitment:
    def __init__(self, hasher: Hasher) -> None:
        self.hasher = hasher
        self.merkle_tree: MerkleTree = None
        self.commitment = None

    def commit(self, vec: List[Any]):
        """
        提交阶段构建 Merkle 树
        """
        # 数据转换成字节列表
        self.merkle_tree = MerkleTree(vec, self.hasher)
        self.commitment = self.merkle_tree.compute_root()

    def open(self, data: Any) -> MerkleProof:
        """
        打开某一数据并生成 Merkle 证明
        """
        # 获取该数据在 Merkle 树中的索引
        index = None
        for i, leaf in enumerate(self.merkle_tree.leaves):
            if leaf == bytes(str(data), 'utf-8'):
                index = i
                break
        if index is None:
            raise ValueError("Data not found in Merkle tree")

        # 获取该数据的 Merkle 证明路径
        proof = self.merkle_tree.get_proof(index)
        return MerkleProof(self, proof, index)

    @staticmethod
    def verify(proof: MerkleProof, data: Any) -> bool:
        """
        静态方法验证 Merkle 证明
        """
        return proof.verify(data)
