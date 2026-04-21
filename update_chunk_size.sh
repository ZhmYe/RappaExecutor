#!/bin/bash

# 检查参数
if [ "$#" -lt 1 ]; then
    echo "使用方法: $0 <CHUNK_SIZE> [NODES_DIR]"
    echo "参数说明:"
    echo "  CHUNK_SIZE : 新的分块大小（正整数）"
    echo "  NODES_DIR  : 节点根目录（可选，默认为当前目录下的 nodes 文件夹）"
    exit 1
fi

CHUNK_SIZE=$1
NODES_DIR=${2:-"./nodes"}

# 检查 CHUNK_SIZE 是否为正整数
if ! [[ "$CHUNK_SIZE" =~ ^[0-9]+$ ]]; then
    echo "错误: CHUNK_SIZE 必须是正整数。"
    exit 1
fi

# 检查目录是否存在
if [ ! -d "$NODES_DIR" ]; then
    echo "错误: 目录 $NODES_DIR 不存在。"
    exit 1
fi

echo "正在将 $NODES_DIR 下所有节点的 NUM_ROW_IN_CHUNK 设置为 $CHUNK_SIZE..."

# 遍历目录下的所有节点
find "$NODES_DIR" -maxdepth 2 -name "config.json" | while read config_file; do
    echo "更新配置文件: $config_file"
    
    # 使用 python 脚本来更新 json 文件，避免直接使用 sed 处理复杂的 json 结构
    python3 -c "
import json
import sys

config_path = '$config_file'
new_chunk_size = $CHUNK_SIZE

try:
    with open(config_path, 'r') as f:
        data = json.load(f)
    
    data['NUM_ROW_IN_CHUNK'] = new_chunk_size
    
    with open(config_path, 'w') as f:
        json.dump(data, f, indent=2)
except Exception as e:
    print(f'Error updating {config_path}: {e}')
"
done

echo "更新完成。"
