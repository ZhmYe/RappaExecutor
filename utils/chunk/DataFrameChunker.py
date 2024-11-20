import pickle
from typing import List

import pandas as pd


class DataFrameChunker:
    def __init__(self):
        pass

    def process(self, data: pd.DataFrame, nb_chunks: int) -> List[bytes]:
        """
        使用 pickle 序列化 DataFrame 并分块
        """
        # 序列化 DataFrame
        serialized_data = pickle.dumps(data)

        # 分块
        chunk_size = (len(serialized_data) + nb_chunks - 1) // nb_chunks
        chunks = [
            serialized_data[i * chunk_size:(i + 1) * chunk_size]
            for i in range(nb_chunks)
        ]
        return chunks

    def restore(self, chunks: List[bytes]) -> pd.DataFrame:
        """
        合并分块并反序列化 DataFrame
        """
        # 合并所有块
        serialized_data = b''.join(chunks)

        # 反序列化
        return pickle.loads(serialized_data)
