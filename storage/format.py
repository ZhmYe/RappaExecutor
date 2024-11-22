# 这是索引里的内容，暂时定为这样，然后将"node_id_sign_slot"作为索引
class StorageIndexItem:
    def __init__(self, node_id, sign, slot, _hash, file_path):
        self.id = node_id
        self.task = {
            "sign": sign,
            "slot": slot
        }
        self.hash = _hash
        self.file_path = file_path


class EncodedChunk:
    def __init__(self, encode_chunks, k, padding_size):
        self.chunks = encode_chunks
        self.k = k
        self.padding_size = padding_size

class ChunksPoolItem:
    def __init__(self, node_id, sign, slot, chunk_index, chunk):
        self.node_id = node_id
        self.sign = sign
        self.slot = slot
        self.chunk_index = chunk_index
        self.chunk = chunk

class LoadChunkItem:
    def __init__(self, node_id, sign, slot, chunk_index, data, padding_size, commitment):
        self.node_id = node_id
        self.slot = slot
        self.sign = sign
        self.index = chunk_index
        self.data = data
        self.padding = padding_size
        self.commitment = commitment
    def format(self):
        return {
            "id": self.node_id,
            "sign": self.sign,
            "slot": self.slot,
            "index": self.index,
            "chunk": {
                "data": self.data,
                "commitment": self.commitment
            },
            "padding": self.padding
        }