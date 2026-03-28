from typing import List
from enum import Enum, auto

from config.config import STORE_METHOD_ENUM
from utils.cryptography.commitment.kzg.kzg_commitment import KZGProof
from utils.cryptography.commitment.merkle.merkle_root import MerkleCommitment, MerkleProof


class ReplicateChunk:
    def __init__(self, col_index, chunk):
        # self.signer = signer
        # self.slot = slot
        # self.row_index = row_index
        self.col_index = col_index
        # self.slot_hash = slot_hash
        self.kzg_proof: KZGProof = None
        self.chunk = chunk
    def bytes(self):
        return self.chunk # todo 这里等待实现
    def set_kzg_proof(self, proof: KZGProof):
        self.kzg_proof = proof

"""
    NOTE: ReplicatePackage 2025-1-8 13:29
    因为这里纠删码必须保证分块大小一致，因此只能按行分块后，对每个行块都ec,然后考虑到 zkp需要证明输入的哈希，也就是行块的哈希，因此行块哈希组成的 merkle_root是整个 slot的 commitment
    然后这里分发的时候将一行的 k 个块发给节点，节点验证k个块的 KZG，然后还原出一个行块，计算其哈希并验证 merkle_proof
    下面的package包含了 k 个 ReplicateChunk
"""
class ReplicatePackage:
    def __init__(self, sign, slot, row_index, store_col_index, slot_hash, merkle_proof: MerkleProof, kzg_commitment, padding_size):
        self.sign = sign
        self.slot = slot
        self.row_index = row_index
        self.store_col_index = store_col_index # 希望节点存下第几块（相对于下面的 list，默认为 0，见 storager.py）
        self.slot_hash = slot_hash
        self.merkle_proof = merkle_proof
        self.kzg_commitment = kzg_commitment # 这里就只需要一个值，类似 root
        self.chunks: List[ReplicateChunk] = []
        self.padding_size = padding_size
        self.store_method = STORE_METHOD_ENUM.EC
    def set_store_method(self, store_method: STORE_METHOD_ENUM):
        self.store_method = store_method
    def add_chunk(self, chunk: ReplicateChunk):
        self.chunks.append(chunk)
    def add_chunks(self, chunks: List[ReplicateChunk]):
        for chunk in chunks:
            self.chunks.append(chunk)







class ReplicateState(Enum):
    SUCCESS = auto()
    INVALID_KZG_PROOFS = auto()
    FAILED = auto()
    # TODO

# 这里记录一个由当前节点生成的数据被分发的记录，便于回收并恢复
# 需要记录的是: 1. 每个chunk被发给了谁; 2. padding_size
# 2025-1-8 12:49 这里新增
# 3. Merkle Proof,这里是一个行块的转发记录，里面包含了其 ec chunk，merkle proof是这个行块恢复后包含在整个 dataframe里的证明
# 4. KZG Proof,每个 ec chunk的 kzg证明
# 其它的数据全部放到CommitSlot里去
class ChunkReplicateRecord:
    # chunk_replicate_list: List[str]是ip的列表，对应index的chunk被发到对应的ip
    def __init__(self,  sign, slot, slot_hash, index, nb_chunk, merkle_proof: MerkleProof, padding_size=0):
        self.sign = sign
        self.slot = slot
        self.slot_hash = slot_hash
        self.replicates = ["" for i in range(nb_chunk)]
        self.padding_size = padding_size
        self.index = index
        self.merkle_proof = merkle_proof
        self.kzg_commitment = None
        self.kzg_proofs: List[KZGProof] = [None for i in range(nb_chunk)]
    def check(self):
        if any([ip == "" for ip in self.replicates]):
            return ReplicateState.FAILED
        # if any([proof is None for proof in self.kzg_proofs]):
        #     return ReplicateState.INVALID_KZG_PROOFS TODO
        return ReplicateState.SUCCESS
    def set_kzg_commitment(self, commitment):
        self.kzg_commitment = commitment # todo 下面的 kzg proof按理要验证下 commitment是否一样
    def set_kzg_proof(self, index, proof: KZGProof):
        self.kzg_proofs[index] = proof
    def set_kzg_proofs(self, proofs: List[KZGProof]):
        if not any([proof is None for proof in proofs]):
            self.kzg_proofs = proofs
        else:
            raise ValueError("Not all proof is not None in given proofs!!!")
    def record_success_replicate(self, index, ip):
        #todo 这里要check
        self.replicates[index] = ip
