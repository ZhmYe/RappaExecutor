#!/bin/bash

"""!!! 在BHExecutionNode目录之外运行该脚本 !!!"""
# 1. CODE_DIRECTORY 需改为BHExecutionNode代码的绝对路径
# 2. 运行命令：./generate_nodes.sh 100 output
#   num_nodes: 生成的节点个数
#   output: 节点生成目录的路径
# 在output目录下生成num_nodes个节点包括其配置文件config.json

# 运行文件后续可改为下载/可执行文件/虚拟环境
CODE_DIRECTORY="/root/BeihangProject/BHExecutionNode" # 运行代码的目录路径

# 检查是否已存在 config.json 文件，如果存在则删除
if [ -f "${CODE_DIRECTORY}/config.json" ]; then
echo "config.json exists in ${CODE_DIRECTORY}, deleting it."
rm -f "${CODE_DIRECTORY}/config.json"
fi

# 检查输入参数
if [ $# -lt 2 ]; then
  echo "Usage: $0 <num_nodes> <output_dir>"
  exit 1
fi

NUM_NODES=$1 # 节点数量
OUTPUT_DIR=$2 # 生成的输出目录

# 检查代码目录是否存在
if [ ! -d "${CODE_DIRECTORY}" ]; then
  echo "Code directory (${CODE_DIRECTORY}) not found!"
  exit 1
fi

# 创建主目录
mkdir -p "${OUTPUT_DIR}/nodes"
if [ $? -ne 0 ]; then
  echo "Failed to create output directory: ${OUTPUT_DIR}"
  exit 1
fi

cd $OUTPUT_DIR/nodes

# 创建每个节点的文件夹结构
for ((i=0; i<NUM_NODES; i++)); do
    NODE_DIR="node$i"
    echo "Creating node directory: $NODE_DIR"
    # 创建节点目录
    mkdir -p $NODE_DIR
    # 复制 ExecutionNode 代码目录
    cp -r "${CODE_DIRECTORY}" "${NODE_DIR}/BHExecutionNode"

    # 创建 config.json 配置文件
    cat <<EOF > $NODE_DIR/BHExecutionNode/config.json
{
  "NODE_ID": $i,
  "EC_PARAMS_N": 9,
  "EC_PARAMS_K": 6,
  "NODE_IP": "127.0.0.1",
  "GRPC_PORT": $((1234 + i*9)),
  "LAYER2_ADDRESS_IP": "127.0.0.1",
  "LAYER_ADDRESS_PORT": $((1235 + i*9)),
  "STORAGE_PATH": "meta"
}
EOF

done
echo "Generated $NUM_NODES nodes."
