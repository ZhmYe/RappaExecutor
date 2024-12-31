from enum import Enum, auto

from utils.cryptography.commitment.merkle_root import MerkleTree
from utils.cryptography.hash.hasher import Hasher


class CommitmentType(Enum):
    MERKLE = auto()
    KZG = auto()
class CommitmentComputer:
    def __init__(self, hasher: Hasher, _lambda=1):
        self._lambda = _lambda
        self.hasher = hasher
    def compute_commitment(self, data, commitment_type: CommitmentType = CommitmentType.MERKLE):
        if commitment_type == CommitmentType.MERKLE:
            return self._compute_merkle_root(data)
        if commitment_type == CommitmentType.KZG:
            return self._compute_kzg_commitment(data)
    def _compute_merkle_root(self, data):
        merkle_tree = MerkleTree(data=data, hasher=self.hasher)
        return merkle_tree.compute_root()
    def _compute_kzg_commitment(self, data):
        pass
    # TODO 这里需要有一个可以给其它节点验证的proof，比如merkle proof,每个chunk一个proof