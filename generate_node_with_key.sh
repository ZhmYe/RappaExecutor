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
  echo "use: $0 <NODES_NUM> [OUTPUT_DIR]"
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

OUTPUT_DIR="${2:-}"
if [[ -z "$OUTPUT_DIR" ]]; then
  OUTPUT_DIR="$PWD"
else
  if [[ "$OUTPUT_DIR" != /* ]]; then
    OUTPUT_DIR="$(cd "$OUTPUT_DIR" && pwd)"
  fi
fi

echo "节点数量：$NODES_NUM"
echo "输出路径：$OUTPUT_DIR"
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

for ((i = 0; i < NODES_NUM; i++)); do
  node_folder="node${i}"

  if [[ -d "$node_folder" ]]; then
    echo "节点 ${node_folder} 已存在，跳过创建。"
    continue
  fi

  echo "创建 ${node_folder}..."
  mkdir -p "$node_folder"
  cp -r "${code_path}" "${node_folder}/"

  node_repo_path="${node_folder}/${executor_dir_name}"
  config_path="${node_repo_path}/config.json"
  node_grpc_port=$((1234 + i * 2))

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
  "OTHER_NODE_GRPC_ADDRESSES": {
EOF

  for ((j = 0; j < NODES_NUM; j++)); do
    if (( j == i )); then
      continue
    fi
    other_grpc_port=$((1234 + j * 2))
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
cd "\$(dirname "\$0")/${executor_dir_name}" || exit 1

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
    bash ./generate_key.sh
  )
done

cat <<EOF >"./start_all.sh"
#!/bin/bash

script_dir="\$(cd "\$(dirname "\$0")" && pwd)"
MODE="\$1"

if [ "\$MODE" = "--debug" ]; then
  echo "启动所有节点 (调试模式)..."
else
  echo "启动所有节点 (生产模式)..."
fi

for (( i=0; i<${NODES_NUM}; i++ )); do
  node_folder="node\${i}"
  node_start_script="\${script_dir}/\${node_folder}/start.sh"

  if [ -f "\$node_start_script" ]; then
    echo "-----------------------------"
    echo "启动节点：\${node_folder}"
    bash "\$node_start_script" "\$MODE" &
  else
    echo "-----------------------------"
    echo "【错误】未检测到节点\${i}的启动脚本: \$node_start_script"
    echo "节点\${i} 启动失败！"
  fi
done

echo "所有节点启动命令已执行完毕。"
EOF
chmod +x "./start_all.sh"

cat <<EOF >"./stop_all.sh"
#!/bin/bash

script_dir="\$(cd "\$(dirname "\$0")" && pwd)"

echo "开始停止所有节点..."

for (( i=0; i<${NODES_NUM}; i++ )); do
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
EOF
chmod +x "./stop_all.sh"

echo "一键启动脚本：${nodes_root}/start_all.sh"
echo "一键停止脚本：${nodes_root}/stop_all.sh"
echo "所有节点与密钥生成完毕。"