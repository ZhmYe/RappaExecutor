import json
import math
import pickle
from io import StringIO

import pandas as pd
from zfec import Encoder, Decoder

from config.config import BHExecutionNodeGlobalConfig
from config.default import DEFAULT_RS_CODE_K, DEFAULT_RS_CODE_N
from logger.logger import logWriter as log
from paradigm.mod import ModelOutputType
from paradigm.storage import ErasureCodeChunks, ErasureCodeChunk

"""
    NOTE: ReedSolomonEncoder 这里暂时就用一种纠删码RS Code
    将给入的数据编码成bytes然后分成若干个chunk，基于这些chunk生成纠删码冗余块
    要注意，编码成bytes以后可能len(bytes)无法被nb_chunk也就是K整除，那么需要填充字段，padding_size记录这一填充长度，最后恢复的时候需要去掉
"""
class ReedSolomonEncoder:
    def __init__(self, k=BHExecutionNodeGlobalConfig.EC_PARAMS_K, n=BHExecutionNodeGlobalConfig.EC_PARAMS_N):
        self.n = n  # 总块数（n）
        self.k = k  # 数据块数（k）
        # self.load_config(config)

    def encode(self, data) -> ErasureCodeChunks:
        """
        对输入数据进行编码：支持 Pandas DataFrame 类型，使用 zfec 编码。
        将 serialized_df 分成 k 个块并生成冗余块。
        :param data: Pandas DataFrame
        :return: 包含数据块和冗余块的字典
        """
        if isinstance(data, pd.DataFrame):
            return self._process_dataframe_with_json(data)
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
            # 按照 chunk_indices 排序
            sorted_chunks = sorted(zip(chunk_indices, encoded_chunks), key=lambda x: x[0])

            # 取排序后的前 k 个块及其索引
            to_decode_indices, to_decode = zip(*sorted_chunks[:self.k])
        # 创建解码器
        decoder = Decoder(self.k, self.n)

        try:
            # 解码
            decoded_chunks = decoder.decode(to_decode, to_decode_indices)
            decoded_data = b''.join(decoded_chunks)
            if padding_size > 0:
                decoded_data = decoded_data[: -padding_size]
            # 反序列化 JSON 数据
            json_str = decoded_data.decode('utf-8')  # 从字节流解码为 JSON 字符串
            restored_df = pd.read_json(StringIO(json_str))  # 反序列化为 DataFrame
            log.write_log("STORAGE", "EC Decoder decode data success...")
            # 反序列化为 DataFrame
            return restored_df
        except Exception as e:
            log.write_log("ERROR", "indices: {}, decoded_data: {}, padding: {}".format(to_decode_indices, decoded_data, padding_size))
            raise ValueError(f"Failed to decode data: {e}")
    # 这里是pickle的实现，但pickle好像是python独有的
    def _process_dataframe_with_pickle(self, df: pd.DataFrame) -> ErasureCodeChunks:
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
        return self._process_serialized_data(serialized_data=serialized_df, chunk_size=chunk_size, padding_size=padding_size, output_type=ModelOutputType.DATAFRAME)

        # # 填充序列化数据到 `chunk_size * k` 的大小
        # padded_data = serialized_df + b'\x00' * padding_size
        #
        # # 将填充后的数据分成 k 个块
        # data_chunks = [
        #     padded_data[i:i + chunk_size] for i in range(0, padded_length, chunk_size)
        # ]
        # ec_encoded_chunks = ErasureCodeChunks(padding_size=padding_size)
        # # 使用 zfec 进行编码
        # encoder = Encoder(self.k, self.n)
        # encoded_chunks = encoder.encode(data_chunks)
        # encoded_chunks = [ErasureCodeChunk(chunk, index) for index, chunk in enumerate(encoded_chunks)]
        # ec_encoded_chunks.add_chunks(encoded_chunks)
        # ec_encoded_chunks.compute_commitment() # todo 计算KZG承诺
        # # 这里需要额外传递padding_size，可以在heartbeat里记录下，这个要能拿到不然还原有问题（不能直接清除后缀0因为可能本来就有若干个）
        # log.write_log("INFO", "EC Encoder encode dataframe to encoded chunks, len(dataframe)={}, len(data_chunks)={}, len(encoded_chunks)={}, padding_size={}".format(len(df), len(data_chunks), len(encoded_chunks), padding_size))
        #
        # return ec_encoded_chunks
    # json好像更通用一点，golang应该能解析
    def _process_dataframe_with_json(self, df: pd.DataFrame) -> ErasureCodeChunks:
        """
        对 Pandas DataFrame 进行编码，确保序列化后的数据分成大小一致的 k 个块。
        使用 zfec 生成冗余块。
        :param df: Pandas DataFrame
        :return: 包含数据块和索引的字典
        """
        # 序列化 DataFrame
        serialized_df = df.to_json()
        serialized_df_bytes = serialized_df.encode('utf-8')  # Convert JSON to bytes
        data_length = len(serialized_df_bytes)

        # 确保分块的大小一致
        chunk_size = math.ceil(data_length / self.k)

        # 计算填充的字节数
        padded_length = chunk_size * self.k
        padding_size = padded_length - data_length

        # # 填充序列化数据到 `chunk_size * k` 的大小
        # padded_data = serialized_df_bytes + b'\x00' * padding_size

        return self._process_serialized_data(serialized_data=serialized_df_bytes, chunk_size=chunk_size, padding_size=padding_size, output_type=ModelOutputType.DATAFRAME)
        # # 将填充后的数据分成 k 个块
        # data_chunks = [
        #     padded_data[i:i + chunk_size] for i in range(0, padded_length, chunk_size)
        # ]
        #
        # # 使用 zfec 进行编码
        # encoder = Encoder(self.k, self.n)
        # encoded_chunks = encoder.encode(data_chunks)
        # # 这里需要额外传递padding_size，可以在heartbeat里记录下，这个要能拿到不然还原有问题（不能直接清除后缀0因为可能本来就有若干个）
        # log.write_log("INFO", "EC Encoder encode dataframe to encoded chunks, len(dataframe)={}, len(data_chunks)={}, len(encoded_chunks)={}, padding_size={}".format(len(df), len(data_chunks), len(encoded_chunks), padding_size))
        #
        # return EncodedChunk(encode_chunks=encoded_chunks, k=self.k, padding_size=padding_size)

    def _process_serialized_data(self, serialized_data, chunk_size, padding_size=0, output_type=ModelOutputType.DATAFRAME) -> ErasureCodeChunks:
        # 填充序列化数据到 `chunk_size * k` 的大小
        padded_data = serialized_data + b'\x00' * padding_size
        padded_length = chunk_size * self.k
        # 将填充后的数据分成 k 个块
        data_chunks = [
            padded_data[i:i + chunk_size] for i in range(0, padded_length, chunk_size)
        ]
        # print([len(chunk) for chunk in data_chunks])
        ec_encoded_chunks = ErasureCodeChunks(padding_size=padding_size, output_type=output_type)
        # 使用 zfec 进行编码
        encoder = Encoder(self.k, self.n)
        encoded_chunks = encoder.encode(data_chunks)
        encoded_chunks = [ErasureCodeChunk(chunk, index) for index, chunk in enumerate(encoded_chunks)]
        ec_encoded_chunks.add_chunks(encoded_chunks)
        ec_encoded_chunks.compute_kzg_commitment() # todo 计算KZG承诺
        # 这里需要额外传递padding_size，可以在heartbeat里记录下，这个要能拿到不然还原有问题（不能直接清除后缀0因为可能本来就有若干个）
        log.write_log("INFO", "EC Encoder encode dataframe to encoded chunks, len(data_chunks)={}, len(encoded_chunks)={}, padding_size={}".format(len(data_chunks), len(encoded_chunks), padding_size))

        return ec_encoded_chunks