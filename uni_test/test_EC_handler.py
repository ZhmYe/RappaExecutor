import pickle
import unittest
import pandas as pd
import numpy as np
import string
import random

from storage.encoder.SimpleECHandler import ECHandler
from utils.chunk.DataFrameChunker import DataFrameChunker
from storage.format import EncodedChunk
from config import default


# Mock configuration for testing
class MockConfig:
    n = 99  # Total number of blocks (data + parity)
    k = 66  # Number of data blocks


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
class TestECEncoder(unittest.TestCase):
    def test_process_dataframe(self):
        # 初始化 ECEncoder
        encoder = ECHandler(MockConfig.k, MockConfig.n)

        # 创建随机 DataFrame
        df = random_dataframe(random.randint(1, 100), random.randint(1,1000))

        # 编码 DataFrame
        encoded_chunk = encoder.encode(df)

        # 验证块数量
        self.assertEqual(len(encoded_chunk.chunks), MockConfig.n,
                         "The number of chunks does not match n.")

        # 将块按序拼接成一个大数据块
        # combined_data = b''.join(encoded_chunk.chunks)
        # print("222", " ", encoded_chunk.chunks)
        # 用纠删码还原数据
        decoded_data = encoder.decode(encoded_chunk.chunks[:MockConfig.k], list(range(MockConfig.k)), encoded_chunk.padding_size)
        # print(decoded_data)
        pd.testing.assert_frame_equal(decoded_data, df, check_dtype=False, obj="Decoded Dataframe does not match the origin Dataframe")

        for i in range(5):
            # 随机选择 k个块进行还原
            selected_indices = random.sample(list(range(MockConfig.n)), MockConfig.k)
            selected_chunks = [encoded_chunk.chunks[i] for i in selected_indices]

            # 解码选定的块
            random_decoded_data = encoder.decode(selected_chunks, selected_indices, encoded_chunk.padding_size)

            pd.testing.assert_frame_equal(random_decoded_data, df, check_dtype=False, obj="Decoded Dataframe does not match the origin Dataframe")
