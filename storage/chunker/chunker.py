import pickle

import pandas as pd

from utils.cryptography.commitment.commitment_computer import CommitmentComputer, CommitmentType
from utils.cryptography.commitment.merkle.merkle_root import MerkleCommitment
from utils.cryptography.hash.hasher import Hasher, HashFunction

"""
    NOTE: Chunker 将生成的文件按行分为若干个chunk，为每个chunk计算hash，然后将这些hash组成merkle tree的叶子节点计算merkle root(commitment)
    随后将这些chunk传递给encoder进行ec编码
"""

class Chunker:
    def __init__(self, hasher:Hasher):
        self.num_row_in_chunk = 5 # 从config中读取 TODO @XQ 在config里补上这个
        self.hasher: Hasher = hasher

    def chunk(self, data):
        # 这里根据data的类型处理
        if isinstance(data, pd.DataFrame):
            return self._chunk_dataframe_data(data)
        else:
            raise ValueError("Unsupported data type. Only Pandas DataFrame is supported.")
        pass
    def _chunk_dataframe_data(self, data: pd.DataFrame):
        # 处理dataframe
        # 按照num_row_in_chunk将dataframe分为若干个chunk，每个chunk使用pickle编码为bytes后计算hash
        # todo @YZM
        """
        将DataFrame按num_row_in_chunk分块，并计算每块的哈希值。

        参数：
            data (pd.DataFrame): 输入的DataFrame。

        返回：
            List[pd.DataFrame]: chunks
            Commitment: Commitment
        """
        num_rows = len(data)
        chunks = []

        for start_row in range(0, num_rows, self.num_row_in_chunk):
            end_row = min(start_row + self.num_row_in_chunk, num_rows)
            chunk = data.iloc[start_row:end_row]


            # 使用pickle将chunk序列化为bytes
            # chunk_bytes = pickle.dumps(chunk)

            # 计算chunk的hash
            # TODO 这里的hasher暂时定为sha256，如果要在zkp里验是否修改为波塞冬哈希比较好
            # chunk_hash = self.hasher.compute(chunk_bytes, hash_function=HashFunction.SHA256)
            # chunk_hashes.append(chunk_hash) # 按序得到所有的hash块

            # TODO 这里最好是一个向量，如果是Pickle的bytes的话是否rust里不能识别
            # 需要一个全局的字典，能够将类别映射成整数，大家的字典需要是一样的 TODO @YZM
            chunks.append(chunk)


        # 根据所有的chunk块计算commitment
        commitment_computer = CommitmentComputer(hasher=self.hasher)
        commitment: MerkleCommitment = commitment_computer.compute_commitment(chunks, commitment_type=CommitmentType.MERKLE) # 这里得到按行分块的结果，每个分块都需要计算一个hash然后组成merkle commitment
        return chunks, commitment
