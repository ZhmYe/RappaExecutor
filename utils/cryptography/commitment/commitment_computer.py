from enum import Enum, auto
from typing import List, Any

from utils.cryptography.commitment.merkle.merkle_root import MerkleCommitment

from utils.cryptography.commitment.kzg.kzg_commitment import KZGCommitment
from utils.cryptography.hash.hasher import Hasher, HashFunction


class CommitmentType(Enum):
    MERKLE = auto()
    KZG = auto()
class CommitmentComputer:
    def __init__(self, hasher: Hasher=Hasher(), _lambda=1):
        self._lambda = _lambda
        self.hasher = hasher
    def compute_commitment(self, data: List[Any], commitment_type: CommitmentType = CommitmentType.MERKLE):
        if commitment_type == CommitmentType.MERKLE:
            return self._compute_merkle_root(data)
        if commitment_type == CommitmentType.KZG:
            return self._compute_kzg_commitment(data)
    def _compute_merkle_root(self, data)->MerkleCommitment:
        merkle_commitment = MerkleCommitment(hf=HashFunction.SHA256)
        merkle_commitment.commit(vec=data)
        return merkle_commitment
        # merkle_commitment.
        # merkle_tree = MerkleTree(data=data, hasher=self.hasher)
        # return merkle_tree.compute_root()
    def _compute_kzg_commitment(self, data: List[bytes])->KZGCommitment:
        kzg_commitment = KZGCommitment()
        kzg_commitment.commit(vec=data)
        return kzg_commitment
    # TODO 这里需要有一个可以给其它节点验证的proof，比如merkle proof,每个chunk一个proof