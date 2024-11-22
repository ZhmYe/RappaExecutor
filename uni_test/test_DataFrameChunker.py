import unittest
from utils.chunk.DataFrameChunker import DataFrameChunker
import pandas as pd
import numpy as np
import string
import random

def random_dataframe(rows: int, cols: int) -> pd.DataFrame:
    """
    生成一个随机 DataFrame，列名唯一且随机字符串，数据为随机浮点数，索引递增。
    """
    # 确保列名唯一
    column_names = set()
    while len(column_names) < cols:
        column_names.add(
            ''.join(random.choices(string.ascii_letters, k=random.randint(3, 8)))
        )
    column_names = list(column_names)

    # 随机生成数据
    data = np.random.rand(rows, cols)

    # 生成递增索引
    index = sorted(random.sample(range(100, 1000), rows))

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

