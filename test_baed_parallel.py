import time
import torch
import json
import networkx as nx
from concurrent.futures import ThreadPoolExecutor
from model.loader import ModelLoader
from utils.function.func import get_model_root
from paradigm.model import ModelEnum

def chunk2json(chunk):
    if isinstance(chunk, list) and len(chunk) > 0 and isinstance(chunk[0], nx.Graph):
        json_chunk = []
        for item in chunk:
            json_chunk.append(nx.node_link_data(item))
        return json.dumps(json_chunk)
    return str(chunk)

def test_baed_parallel_speed():
    model_name = "BAED"
    model_root = get_model_root()
    loader = ModelLoader(model_root)
    
    print(f"Loading model {model_name}...")
    is_cuda = torch.cuda.is_available()
    instance = loader.load(model_name, is_cuda)
    print(f"Model loaded. CUDA: {is_cuda}")
    
    total_samples = 12800
    num_parallel = 1
    samples_per_task = total_samples // num_parallel
    
    print(f"Starting parallel synthesis test: {num_parallel} tasks, {samples_per_task} samples each (total {total_samples}).")
    
    start_time = time.time()
    
    results = []
    with ThreadPoolExecutor(max_workers=num_parallel) as executor:
        futures = [executor.submit(instance.generate_output, samples_per_task) for _ in range(num_parallel)]
        for future in futures:
            results.append(future.result())
            
    end_time = time.time()
    duration = end_time - start_time
    
    # 合并结果并存入 pickle
    all_graphs = []
    for res in results:
        all_graphs.extend(res.output)
    
    import pickle
    import os
    file_name = f"baed_generate_{total_samples}.pkl"
    with open(file_name, 'wb') as f:
        pickle.dump(all_graphs, f)
    
    file_size_mb = len(pickle.dumps(all_graphs)) / (1024 * 1024)
    synthesis_speed = file_size_mb / duration
    
    print("-" * 30)
    print(f"Parallel Synthesis Test Finished")
    print(f"Total Graphs: {len(all_graphs)}")
    print(f"Total Time: {duration:.2f} s")
    print(f"Pickle File Size: {file_size_mb:.2f} MB")
    print(f"Synthesis Speed (based on Pickle): {synthesis_speed:.2f} MB/s")

if __name__ == "__main__":
    test_baed_parallel_speed()
