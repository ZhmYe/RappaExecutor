from io import StringIO

from config.config import BHExecutionNodeGlobalConfig
from paradigm.mod import ModelOutputType
from paradigm.storage import ErasureCodeChunks, ErasureCodeRecoverError
from zfec import Decoder
import pandas as pd
from logger.logger import logWriter as log

class ReedSolomonDecoder:
    def __init__(self, k=BHExecutionNodeGlobalConfig.EC_PARAMS_K, n=BHExecutionNodeGlobalConfig.EC_PARAMS_N):
        self.k = k
        self.n = n
    def decode(self, encoded_chunks: ErasureCodeChunks):
        decoder = Decoder(self.k, self.n)
        decoded_chunks, error = encoded_chunks.recover(decoder=decoder)
        if error != ErasureCodeRecoverError.NONE:
            return decoded_chunks, error
        decoded_data = b''.join(decoded_chunks)
        # 如果decoded_chunks被正常解码
        if encoded_chunks.output_type == ModelOutputType.DATAFRAME:
            if encoded_chunks.padding_size > 0:
                decoded_data = decoded_data[: -encoded_chunks.padding_size]
                # 反序列化 JSON 数据
            json_str = decoded_data.decode('utf-8')  # 从字节流解码为 JSON 字符串
            restored_df = pd.read_json(StringIO(json_str))  # 反序列化为 DataFrame
            log.write_log("STORAGE", "EC Decoder decode data success...")
            # 反序列化为 DataFrame
            return restored_df, ErasureCodeRecoverError.NONE
        else:
            raise ValueError("Only support output_type=ModelOutputType.DATAFRAME")
