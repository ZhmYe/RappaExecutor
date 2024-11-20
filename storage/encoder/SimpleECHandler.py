import math
import pickle
import pandas as pd
from zfec import Encoder, Decoder

from config.default import DEFAULT_RS_CODE_K, DEFAULT_RS_CODE_N
from logger.logger import logWriter as log
from storage.format import EncodedChunk


class ECHandler:
    def __init__(self, k, n):
        self.n = n  # 总块数（n）
        self.k = k  # 数据块数（k）
        # self.load_config(config)

    # def load_config(self, config):
    #     """
    #     加载配置，设置总块数 (n) 和数据块数 (k)
    #     """
    #     if config and config.n and config.k:
    #         self.n = config.n
    #         self.k = config.k

    def encode(self, data) -> EncodedChunk:
        """
        对输入数据进行编码：支持 Pandas DataFrame 类型，使用 zfec 编码。
        将 serialized_df 分成 k 个块并生成冗余块。
        :param data: Pandas DataFrame
        :return: 包含数据块和冗余块的字典
        """
        if isinstance(data, pd.DataFrame):
            return self._process_dataframe(data)
        else:
            raise ValueError("Unsupported data type. Only Pandas DataFrame is supported.")

    def decode(self, encoded_chunks, chunk_indices, padding_size) -> pd.DataFrame:
        """
        从编码后的块中恢复原始数据。
        :param padding_size: 填充的0的个数
        :param encoded_chunks: 已编码的块列表（bytes）
        :param chunk_indices: 块对应的索引（list of int）
        :return: 恢复的 Pandas DataFrame
        """
        # to_decode = encoded_chunks
        if len(encoded_chunks) < self.k:
            raise ValueError("Insufficient chunks to decode. At least k chunks are required.")
        else:
            """
            zfec的纠删码只能接受k个数据块，如果传进来的数据块多了，就选择其中前k个，（这里我们不暂时不考虑作恶）
            """
            to_decode = encoded_chunks[:self.k]
            to_decode_indices = chunk_indices[:self.k]
        # 创建解码器
        decoder = Decoder(self.k, self.n)

        try:
            # 解码
            decoded_chunks = decoder.decode(to_decode, to_decode_indices)
            decoded_data = b''.join(decoded_chunks)
            decoded_data = decoded_data[: -padding_size]
            log.write_log("INFO", "EC Decoder")
            # 反序列化为 DataFrame
            return pickle.loads(decoded_data)
        except Exception as e:
            raise ValueError(f"Failed to decode data: {e}")

    def _process_dataframe(self, df: pd.DataFrame) -> EncodedChunk:
        """
        对 Pandas DataFrame 进行编码，确保序列化后的数据分成大小一致的 k 个块。
        使用 zfec 生成冗余块。
        :param df: Pandas DataFrame
        :return: 包含数据块和索引的字典
        """
        # 序列化 DataFrame
        serialized_df = pickle.dumps(df)
        data_length = len(serialized_df)

        # 确保分块的大小一致
        chunk_size = math.ceil(data_length / self.k)

        # 计算填充的字节数
        padded_length = chunk_size * self.k
        padding_size = padded_length - data_length

        # 填充序列化数据到 `chunk_size * k` 的大小
        padded_data = serialized_df + b'\x00' * padding_size

        # 将填充后的数据分成 k 个块
        data_chunks = [
            padded_data[i:i + chunk_size] for i in range(0, padded_length, chunk_size)
        ]

        # 使用 zfec 进行编码
        encoder = Encoder(self.k, self.n)
        encoded_chunks = encoder.encode(data_chunks)
        # 这里需要额外传递padding_size，可以在heartbeat里记录下，这个要能拿到不然还原有问题（不能直接清除后缀0因为可能本来就有若干个）
        log.write_log("INFO", "EC Encoder encode dataframe to encoded chunks, len(dataframe)={}, len(data_chunks)={}, len(encoded_chunks)={}, padding_size={}".format(len(df), len(data_chunks), len(encoded_chunks), padding_size))

        return EncodedChunk(encode_chunks=encoded_chunks, k=self.k, padding_size=padding_size)
