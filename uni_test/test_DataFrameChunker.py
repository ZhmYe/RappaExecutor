import unittest
from utils.chunk.DataFrameChunker import DataFrameChunker
import pandas as pd
import numpy as np
import string
import random


def random_dataframe(rows: int, cols: int) -> pd.DataFrame:
    """
    生成一个随机 DataFrame，列名为随机字符串，数据为随机浮点数
    """
    column_names = [
        ''.join(random.choices(string.ascii_letters, k=random.randint(3, 8)))
        for _ in range(cols)
    ]
    data = np.random.rand(rows, cols)
    index = np.random.randint(100, 1000, size=rows)
    return pd.DataFrame(data, columns=column_names, index=index)


class TestDataFrameChunker(unittest.TestCase):

    def test_chunker(self):
        chunker = DataFrameChunker()

        # 创建随机 DataFrame
        rows, cols = random.randint(1, 1000), random.randint(1, 100)
        df = random_dataframe(rows, cols)

        # 分块处理
        nb_chunks = random.randint(1, 10)
        chunks = chunker.process(df, nb_chunks)

        # 通过分块恢复 DataFrame
        restored_df = chunker.restore(chunks)

        # 验证 DataFrame 还原是否正确
        pd.testing.assert_frame_equal(df, restored_df)

