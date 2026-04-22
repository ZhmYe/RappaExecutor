import time
import torch
import json
import networkx as nx
from model.loader import ModelLoader
from utils.function.func import get_model_root
from paradigm.model import ModelEnum
import os
import sys
import pickle

def chunk2json(chunk):
    if isinstance(chunk, list) and len(chunk) > 0 and isinstance(chunk[0], nx.Graph):
        json_chunk = []
        for item in chunk:
            json_chunk.append(nx.node_link_data(item))
        return json.dumps(json_chunk)
    return json.dumps(chunk)

def test_baed_speed():
    model_name = "BAED"
    model_root = get_model_root()
    loader = ModelLoader(model_root)
    
    print(f"Loading model {model_name}...")
    is_cuda = torch.cuda.is_available()
    instance = loader.load(model_name, is_cuda)
    print(f"Model loaded. CUDA: {is_cuda}")
    
    total_samples = 1000
    
    print(f"Starting synthesis test: total {total_samples} samples (internal batching).")
    
    start_time = time.time()
    output = instance.generate_output(total_samples)
    duration = time.time() - start_time
    # 获取数据合成文件大小
    file_size = len(pickle.dumps(output)) / (1024 * 1024)  # 转换为MB
    print(f"数据合成文件大小：{file_size:.2f} MB")
    # 计算数据合成速度
    synthesis_speed = file_size / duration
    print(f"数据合成速度：{synthesis_speed:.2f} MB/s")
    print("save finish")  



if __name__ == "__main__":
    test_baed_speed()
