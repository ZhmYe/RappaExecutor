#!/bin/bash

set -euo pipefail

code_path="$(cd "$(dirname "$0")" && pwd)"
executor_dir_name="$(basename "$code_path")"
key_script_path="${code_path}/generate_key.sh"
host_sk_file="host_sk.key"
host_pk_file="host_pk.key"
host_key_script="generate_host_keys.py"

NODES_NUM="${1:-}"
if [[ -z "$NODES_NUM" ]]; then
  echo "使用方法: $0 <NODES_NUM> [OUTPUT_DIR] [START_PORT] [PORT_INTERVAL] [START_NODE_ID]"
  echo "参数说明:"
  echo "  NODES_NUM    : 要生成的节点数量（正整数）"
  echo "  OUTPUT_DIR   : 节点输出目录（可选，默认为当前目录）"
  echo "  START_PORT   : 起始端口号（可选，默认为 1234）"
  echo "  PORT_INTERVAL: 端口间隔（可选，默认为 2）"
  echo "  START_NODE_ID: 起始节点编号（可选，默认为 0）"
  echo "  CHUNK_SIZE   : 每个分块的数据行数（可选，默认为 20）"
  exit 1
fi

if ! [[ "$NODES_NUM" =~ ^[0-9]+$ ]]; then
  echo "错误: NODES_NUM 必须是正整数。" >&2
  exit 1
fi

if (( NODES_NUM <= 0 )); then
  echo "错误: NODES_NUM 必须大于 0。" >&2
  exit 1
fi

if [[ ! -f "$key_script_path" ]]; then
  echo "未找到密钥生成脚本: $key_script_path" >&2
  exit 1
fi

OUTPUT_DIR="${2:-.}"
if [[ "$OUTPUT_DIR" == "." ]]; then
  OUTPUT_DIR="$PWD"
elif [[ "$OUTPUT_DIR" != /* ]]; then
  mkdir -p "$OUTPUT_DIR"
  OUTPUT_DIR="$(cd "$OUTPUT_DIR" && pwd)"
fi

START_PORT="${3:-1234}"
PORT_INTERVAL="${4:-2}"
START_NODE_ID="${5:-0}"
CHUNK_SIZE="${6:-20}"

echo "节点数量：$NODES_NUM"
echo "输出路径：$OUTPUT_DIR"
echo "起始端口：$START_PORT"
echo "端口间隔：$PORT_INTERVAL"
echo "起始编号：$START_NODE_ID"
echo "分块大小：$CHUNK_SIZE"
echo "-----------------------------"

echo "检查主机密钥是否存在..."
cd $code_path || exit 1
if [[ ! -f "$host_sk_file" || ! -f "$host_pk_file" ]]; then
  echo "未检测到主机密钥文件，正在生成主机密钥..."
  if [[ ! -f "$host_key_script" ]]; then
    echo "【错误】未找到主机密钥生成脚本：$host_key_script" >&2
    exit 1
  fi
  python3 "$host_key_script"
  echo "主机密钥生成完成。"
else
  echo "主机密钥已存在，跳过生成。"
fi
echo "-----------------------------"

nodes_root="${OUTPUT_DIR}/nodes"
mkdir -p "$nodes_root"
cd "$nodes_root" || exit 1

echo "节点主目录：$(pwd)"

GENERATE_F=$(((NODES_NUM - 1) / 3))
EC_PARAMS_N=$((2 * GENERATE_F + 1))
EC_PARAMS_K=$((GENERATE_F + 1))

MAX_JOBS=10
for ((i = START_NODE_ID; i < START_NODE_ID + NODES_NUM; i++)); do
  (
    node_folder="node${i}"

    if [[ -d "$node_folder" ]]; then
      echo "节点 ${node_folder} 已存在，跳过创建。"
      exit 0
    fi

    echo "创建 ${node_folder}..."
    mkdir -p "$node_folder"
    if command -v rsync >/dev/null 2>&1; then
      rsync -a --exclude='nodes' --exclude='__pycache__' --exclude='.git' --exclude='model/TRADINGNET' "${code_path}/" "${node_folder}/${executor_dir_name}/"
    else
      cp -r "${code_path}" "${node_folder}/"
      rm -rf "${node_folder}/${executor_dir_name}/__pycache__"
      rm -rf "${node_folder}/${executor_dir_name}/model/TRADINGNET"
    fi

    node_repo_path="${node_folder}/${executor_dir_name}"
    config_path="${node_repo_path}/config.json"
    node_grpc_port=$((START_PORT + (i - START_NODE_ID) * PORT_INTERVAL))

    cat <<EOF >"$config_path"
{
  "NODE_ID": $i,
  "EC_PARAMS_N": $EC_PARAMS_N,
  "EC_PARAMS_K": $EC_PARAMS_K,
  "NODE_IP": "127.0.0.1",
  "GRPC_PORT": $node_grpc_port,
  "LAYER2_ADDRESS_IP": "127.0.0.1",
  "LAYER_ADDRESS_PORT": 50051,
  "NUM_PROCESS_WORKER": 1,
  "STORAGE_PATH": "meta",
  "IS_CUDA": true,
  "IS_RECOVERY": true,
  "NUM_ROW_IN_CHUNK": $CHUNK_SIZE,
  "OTHER_NODE_GRPC_ADDRESSES": {
EOF

    for ((j = START_NODE_ID; j < START_NODE_ID + NODES_NUM; j++)); do
      if (( j == i )); then
        continue
      fi
      other_grpc_port=$((START_PORT + (j - START_NODE_ID) * PORT_INTERVAL))
      cat <<EOF >>"$config_path"
    "$j": {
      "IP": "127.0.0.1",
      "PORT": $other_grpc_port
    },
EOF
    done

    sed -i '$s/,//' "$config_path"
    cat <<'EOF' >>"$config_path"
  }
}
EOF

    cat <<EOF >"${node_folder}/start.sh"
#!/bin/bash
MODE="\$1"
GPU_ID="\$2"

cd "\$(dirname "\$0")/${executor_dir_name}" || exit 1

if [ -n "\$GPU_ID" ]; then
  export CUDA_VISIBLE_DEVICES="\$GPU_ID"
  echo "节点 node${i}：分配使用 GPU \$GPU_ID"
fi

echo "启动节点：node${i}"
if [ "\$MODE" = "--debug" ]; then
  echo "节点 node${i}：进入调试模式..."
  python3 main.py --debug &
else
  echo "节点 node${i}：进入生产模式..."
  python3 main.py &
fi

echo "\$!" > "../node.pid"
EOF
    chmod +x "${node_folder}/start.sh"

    cat <<EOF >"${node_folder}/stop.sh"
#!/bin/bash

SHELL_FOLDER="\$(cd "\$(dirname "\$0")" && pwd)"
cd "\${SHELL_FOLDER}" || exit 1

node_name="node${i}"
pid_file="\${SHELL_FOLDER}/node.pid"

if [ ! -f "\$pid_file" ]; then
    echo "【INFO】\${node_name} 未检测到 pid 文件，可能未启动或已停止。"
    exit 0
fi

pid=\$(cat "\$pid_file")
echo "尝试停止 \${node_name} (PID=\$pid)..."
kill "\$pid"

try_times=10
j=0
while [ \$j -lt \$try_times ]; do
    sleep 1
    if ! ps -p "\$pid" > /dev/null 2>&1; then
        echo "【INFO】\${node_name} 已停止。"
        rm -f "\$pid_file"
        exit 0
    fi
    ((j=j+1))
done

echo "【WARN】停止 \${node_name} 超时，请手动检查或使用 kill -9。"
exit 1
EOF
    chmod +x "${node_folder}/stop.sh"

    echo "为 node${i} 生成密钥与证书..."
    (
      cd "$node_repo_path"
      bash ./generate_key.sh > /dev/null 2>&1
    )
    echo "节点 node${i} 创建并初始化完成。"
  ) &

  if (( (i + 1) % MAX_JOBS == 0 )); then
    wait
  fi
done
wait

# 创建参数化的启动脚本
cat <<'EOF' >"./start_para.sh"
#!/bin/bash

script_dir="$(cd "$(dirname "$0")" && pwd)"
PARALLEL="${1:-1}"
TIMEOUT="${2:-600}"
MODE="${3:-}"

# 获取节点数量
NODES_NUM=$(find "$script_dir" -mindepth 1 -maxdepth 1 -type d -name "node*" | wc -l)

# 检查 GPU 数量
if command -v nvidia-smi &> /dev/null; then
  GPU_COUNT=$(nvidia-smi -L | wc -l)
else
  GPU_COUNT=0
fi

usage() {
  echo "使用方法: $0 [PARALLEL] [TIMEOUT] [MODE]"
  echo "参数说明:"
  echo "  PARALLEL : 并行启动的节点数量，默认1（串行）"
  echo "  TIMEOUT  : 等待节点加载的超时时间（秒），默认600秒"
  echo "  MODE     : 启动模式，--debug 或 空（默认生产模式）"
  echo ""
  echo "示例:"
  echo "  $0                    # 串行启动所有节点（生产模式）"
  echo "  $0 2                  # 并行启动2个节点（生产模式）"
  echo "  $0 2 300              # 并行启动2个节点，超时300秒"
  echo "  $0 2 300 --debug      # 并行启动2个节点，超时300秒（调试模式）"
}

if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
  usage
  exit 0
fi

if ! [[ "$PARALLEL" =~ ^[0-9]+$ ]] || [ "$PARALLEL" -lt 1 ]; then
  echo "错误: PARALLEL 必须是大于0的整数。" >&2
  usage
  exit 1
fi

if ! [[ "$TIMEOUT" =~ ^[0-9]+$ ]] || [ "$TIMEOUT" -lt 60 ]; then
  echo "错误: TIMEOUT 必须是大于60的整数。" >&2
  usage
  exit 1
fi

if [ "$MODE" = "--debug" ]; then
  echo "智能启动所有节点 (调试模式)..."
else
  echo "智能启动所有节点 (生产模式)..."
fi
echo "并行度: $PARALLEL"
echo "超时时间: ${TIMEOUT}秒"
echo "总节点数: ${NODES_NUM}"
if [ "$GPU_COUNT" -gt 0 ]; then
  echo "检测到 GPU 数量: $GPU_COUNT，将按数量平分节点 GPU 启动。"
else
  echo "未检测到 GPU，将按默认方式启动。"
fi
echo "-----------------------------"

if [ "$NODES_NUM" -eq 0 ]; then
  echo "错误: 未找到任何节点目录！"
  exit 1
fi

# 查找最新日志文件的函数
find_latest_log() {
  local node_id="$1"
  local log_dir="${script_dir}/node${node_id}/RappaExecutor/logs"
  local latest_log=""
  
  if [ -d "$log_dir" ]; then
    latest_log=$(ls -t "$log_dir" | grep "\.log$" | head -1)
    if [ -n "$latest_log" ]; then
      echo "${log_dir}/${latest_log}"
    fi
  fi
}

# 等待节点模型加载完成的函数
wait_for_model_loading() {
  local node_id="$1"
  local node_name="node${node_id}"
  local start_time=$(date +%s)
  local log_file=""
  
  echo "等待节点 ${node_name} 模型加载..."
  
  # 先等待一段时间，让节点开始生成日志
  sleep 10
  
  while true; do
    local current_time=$(date +%s)
    local elapsed=$((current_time - start_time))
    
    if [ $elapsed -gt $TIMEOUT ]; then
      echo "【错误】节点 ${node_name} 模型加载超时（${TIMEOUT}秒）！"
      return 1
    fi
    
    # 查找最新的日志文件
    log_file=$(find_latest_log "$node_id")
    
    if [ -n "$log_file" ] && [ -f "$log_file" ]; then
      if grep -q "Load All Supported Model Success..." "$log_file"; then
        echo "节点 ${node_name} 模型加载完成！"
        return 0
      fi
      # 如果找到了日志文件但还没有成功消息，显示一些进度信息
      if [ $((elapsed % 30)) -eq 0 ]; then
        echo "节点 ${node_name} 仍在加载中... 已等待 ${elapsed} 秒"
      fi
    else
      # 如果还没有日志文件，显示等待信息
      if [ $((elapsed % 30)) -eq 0 ]; then
        echo "节点 ${node_name} 正在启动... 已等待 ${elapsed} 秒"
      fi
    fi
    
    sleep 5
  done
}

# 启动单个节点的函数
start_single_node() {
  local node_id="$1"
  local gpu_id="$2"
  local node_folder="node${node_id}"
  local node_start_script="${script_dir}/${node_folder}/start.sh"

  if [ ! -f "$node_start_script" ]; then
    echo "【错误】未检测到节点${node_id}的启动脚本: $node_start_script"
    return 1
  fi

  echo "启动节点：${node_folder} (GPU: ${gpu_id:-None})"
  bash "$node_start_script" "$MODE" "$gpu_id" &
  local node_pid=$!
  
  # 等待节点模型加载完成
  if wait_for_model_loading "$node_id"; then
    wait $node_pid  # 等待进程正常结束
    return 0
  else
    kill $node_pid 2>/dev/null  # 超时则杀死进程
    return 1
  fi
}

# 获取所有节点 ID
node_ids=($(find "$script_dir" -mindepth 1 -maxdepth 1 -type d -name "node*" | sed 's/.*node//' | sort -n))

# 按批次启动节点
current_batch=()
success_count=0
fail_count=0

for i in "${!node_ids[@]}"; do
  node_id="${node_ids[$i]}"
  
  # 计算 GPU ID
  if [ "$GPU_COUNT" -gt 0 ]; then
    gpu_id=$(( i % GPU_COUNT ))
  else
    gpu_id=""
  fi

  # 启动当前节点
  start_single_node "$node_id" "$gpu_id" &
  current_batch+=($!)
  
  # 如果达到并行度，等待当前批次完成
  if [ ${#current_batch[@]} -eq "$PARALLEL" ]; then
    for pid in "${current_batch[@]}"; do
      if wait $pid; then
        ((success_count++))
      else
        ((fail_count++))
      fi
    done
    current_batch=()
    echo "当前批次完成，成功: ${success_count}, 失败: ${fail_count}"
  fi
done

# 等待剩余批次完成
if [ ${#current_batch[@]} -gt 0 ]; then
  for pid in "${current_batch[@]}"; do
    if wait $pid; then
      ((success_count++))
    else
      ((fail_count++))
    fi
  done
fi

echo "================================="
echo "所有节点启动完成！"
echo "成功: ${success_count}, 失败: ${fail_count}"
echo "================================="

if [ "$fail_count" -gt 0 ]; then
  exit 1
fi
EOF
chmod +x "./start_para.sh"

# 保留原有的并行启动脚本
cat <<EOF >"./start_all.sh"
#!/bin/bash

script_dir="\$(cd "\$(dirname "\$0")" && pwd)"
MODE="\$1"

# 检查 GPU 数量
if command -v nvidia-smi &> /dev/null; then
  GPU_COUNT=\$(nvidia-smi -L | wc -l)
else
  GPU_COUNT=0
fi

if [ "\$GPU_COUNT" -gt 0 ]; then
  echo "检测到 \$GPU_COUNT 个 GPU，将按数量平分节点 GPU 启动。"
else
  echo "未检测到 GPU，将按默认方式启动。"
fi

if [ "\$MODE" = "--debug" ]; then
  echo "并行启动所有节点 (调试模式)..."
else
  echo "并行启动所有节点 (生产模式)..."
fi
echo "警告: 此脚本会同时启动所有节点，在无GPU环境下可能导致CPU过载！"
echo "推荐使用: ./start_para.sh [MODE] [PARALLEL] [TIMEOUT]"

for (( i=${START_NODE_ID}; i<${START_NODE_ID}+${NODES_NUM}; i++ )); do

  node_folder="node\${i}"
  node_start_script="\${script_dir}/\${node_folder}/start.sh"

  if [ -f "\$node_start_script" ]; then
    echo "-----------------------------"
    echo "启动节点：\${node_folder}"
    
    # 计算该节点使用的 GPU ID
    if [ "\$GPU_COUNT" -gt 0 ]; then
      GPU_ID=\$(( (i - ${START_NODE_ID}) % GPU_COUNT ))
    else
      GPU_ID=""
    fi
    
    bash "\$node_start_script" "\$MODE" "\$GPU_ID" &
  else
    echo "-----------------------------"
    echo "【错误】未检测到节点\${i}的启动脚本: \$node_start_script"
    echo "节点\${i} 启动失败！"
  fi
done

echo "所有节点启动命令已执行完毕。"
echo "注意: 节点正在后台启动，使用 ./stop_all.sh 停止所有节点"
EOF
chmod +x "./start_all.sh"

cat <<EOF >"./stop_all.sh"
#!/bin/bash

script_dir="\$(cd "\$(dirname "\$0")" && pwd)"

echo "开始停止所有节点..."

for (( i=${START_NODE_ID}; i<${START_NODE_ID}+${NODES_NUM}; i++ )); do

  node_folder="node\${i}"
  node_stop_script="\${script_dir}/\${node_folder}/stop.sh"

  if [ -f "\$node_stop_script" ]; then
    bash "\$node_stop_script" &
  else
    echo "-----------------------------"
    echo "【错误】未检测到节点\${i}的停止脚本: \$node_stop_script"
    echo "节点\${i} 停止失败！"
  fi
done

wait
echo "所有节点停止命令已执行完毕。"
EOF
chmod +x "./stop_all.sh"

echo "节点生成完成！"
echo ""
echo "启动脚本说明:"
echo "1. 并行度控制启动脚本: ${nodes_root}/start_para.sh"
echo "   用法: ./start_para.sh [MODE] [PARALLEL] [TIMEOUT]"
echo "   示例: ./start_para.sh 5 300"
echo ""
echo "2. 一键并行启动脚本: ${nodes_root}/start_all.sh"
echo "   用法: ./start_all.sh [MODE]"
echo "   警告: 在无GPU环境下可能导致CPU过载！"
echo ""
echo "3. 停止脚本: ${nodes_root}/stop_all.sh"
echo ""
echo "所有节点与密钥生成完毕。"