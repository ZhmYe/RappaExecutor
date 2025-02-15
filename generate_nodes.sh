#!/bin/bash

set -e

###############################################################################
# 1. 参数解析
###############################################################################
code_path="$(cd "$(dirname "$0")" && pwd)" # 获取Executor代码的绝对路径。
NODES_NUM="$1"                             # 第一个参数：节点数量
if [ -z "$NODES_NUM" ]; then
  echo "use: $0 <NODES_NUM> [OUTPUT_DIR]"
  exit 1
fi

OUTPUT_DIR="$2" # 第二个参数：输出目录
# 如果用户没有指定输出目录，则默认使用当前工作目录
if [ -z "$OUTPUT_DIR" ]; then
  OUTPUT_DIR="$PWD"
else
  # 如果指定了输出目录，判断是绝对路径还是相对路径
  if [[ "$OUTPUT_DIR" == /* ]]; then
    # 如果以 "/" 开头则是绝对路径，直接使用即可
    :
  else
    # 否则视为相对路径，将其转换为绝对路径
    OUTPUT_DIR="$(cd "$OUTPUT_DIR" && pwd)"
  fi
fi

echo "节点数量：$NODES_NUM"
echo "输出路径：$OUTPUT_DIR"
echo "-----------------------------"

###############################################################################
# 2. 创建 nodes 主目录（OUTPUT_DIR下）
###############################################################################
OUTPUT_DIR="$OUTPUT_DIR/nodes"
mkdir -p "$OUTPUT_DIR"
cd "$OUTPUT_DIR" || exit 1
echo "节点主目录：$(pwd)"

###############################################################################
# 3. 为每个节点创建目录结构，复制代码并覆盖 config.json、生成启动/终止脚本
###############################################################################
GENERATE_F=$((($NODES_NUM - 1) / 3))

for ((i = 0; i < NODES_NUM; i++)); do
  node_folder="node${i}"
  mkdir -p "$node_folder"
  cp -r "${code_path}" "${node_folder}/"

  # 创建 config.json
  config_path="${node_folder}/RappaExecutor/config.json"
  cat <<EOF >$config_path
{
  "NODE_ID": $i,
  "EC_PARAMS_N": $((2 * $GENERATE_F + 1)),
  "EC_PARAMS_K": $(($GENERATE_F + 1)),
  "NODE_IP": "127.0.0.1",
  "GRPC_PORT": $((1234 + i * 2)),
  "LAYER2_ADDRESS_IP": "127.0.0.1",
  "LAYER_ADDRESS_PORT": 50051,
  "NUM_PROCESS_WORKER": 1,
  "STORAGE_PATH": "meta",
  "OTHER_NODE_GRPC_ADDRESSES": {
EOF

  # 生成NODE_ADDRESSES，排除当前节点
  first=true
  for ((j = 0; j < NODES_NUM; j++)); do
    if [ $j -ne $i ]; then
      cat<<EOF >>$config_path
    "$j": {
      "IP": "127.0.0.1",
      "PORT": $((1234 + j * 2))
    },
EOF
    fi
  done

  # 处理末尾格式
  sed -i '$s/,//' $config_path
  cat<<EOL >>$config_path
  }
}
EOL

  # 创建单个节点的启动脚本 start.sh
  cat <<EOF >"${node_folder}/start.sh"
#!/bin/bash

# 读取第一个参数，判断是否为 --debug
MODE="\$1"

# 切换到 RappaExecutor 目录
cd "\$(dirname "\$0")/RappaExecutor" || exit 1

echo "启动节点：node${i}"

# 以后台方式启动，并将进程 PID 写入 node.pid（放到上一级目录 nodeX 下）
if [ "\$MODE" = "--debug" ]; then
  echo "节点 node${i}：进入调试模式..."
  python3 main.py --debug &
else
  echo "节点 node${i}：进入生产模式..."
  python3 main.py &
fi

# 将后台进程的 PID 写入 ../node.pid 文件
echo "\$!" > "../node.pid"
EOF
  chmod +x "${node_folder}/start.sh"

  # 创建单个节点的停止脚本 stop.sh
  cat <<EOF >"${node_folder}/stop.sh"
#!/bin/bash

# 切换到当前脚本所在目录（nodeX）
SHELL_FOLDER="\$(cd "\$(dirname "\$0")" && pwd)"
cd "\${SHELL_FOLDER}" || exit 1

node_name="node${i}"
pid_file="\${SHELL_FOLDER}/node.pid"

# 如果没找到 node.pid，说明进程可能不在运行
if [ ! -f "\$pid_file" ]; then
    echo "【INFO】\${node_name} 未检测到 pid 文件，可能未启动或已停止。"
    exit 0
fi

pid=\$(cat "\$pid_file")
echo "尝试停止 \${node_name} (PID=\$pid)..."
kill "\$pid"

# 等待进程退出，最多尝试 10 次
try_times=10
j=0
while [ \$j -lt \$try_times ]; do
    sleep 1
    # 如果该 pid 不再存活，说明停止成功
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
done

###############################################################################
# 4. 生成一键启动脚本：start_all.sh
###############################################################################
cat <<EOF >"./start_all.sh"
#!/bin/bash

# 1) 获取脚本所在目录绝对路径（确保可在任意路径下执行）
script_dir="\$(cd "\$(dirname "\$0")" && pwd)"

# 2) 读取第一个参数，如果是 --debug，则所有节点均进入调试模式；否则默认生产模式
MODE="\$1"

if [ "\$MODE" = "--debug" ]; then
  echo "启动所有节点 (调试模式)..."
else
  echo "启动所有节点 (生产模式)..."
fi

# 3) 检查并启动每个节点
for (( i=0; i<${NODES_NUM}; i++ )); do
  node_folder="node\${i}"
  node_start_script="\${script_dir}/\${node_folder}/start.sh"

  if [ -f "\$node_start_script" ]; then
    echo "-----------------------------"
    echo "启动节点：\${node_folder}"
    # 将 MODE 传给单个节点的 start.sh
    bash "\$node_start_script" "\$MODE" &
  else
    echo "-----------------------------"
    echo "【错误】未检测到节点\${i}的启动脚本: \$node_start_script"
    echo "节点\${i} 启动失败！"
  fi
done

echo "所有节点启动命令已执行完毕。"
EOF
chmod +x "${OUTPUT_DIR}/start_all.sh"

echo "一键启动脚本：${OUTPUT_DIR}/start_all.sh"

###############################################################################
# 5. 生成一键停止脚本：stop_all.sh
###############################################################################
cat <<EOF >"./stop_all.sh"
#!/bin/bash

# 获取脚本所在目录绝对路径
script_dir="\$(cd "\$(dirname "\$0")" && pwd)"

echo "开始停止所有节点..."

# 遍历所有节点目录
for (( i=0; i<${NODES_NUM}; i++ )); do
  node_folder="node\${i}"
  node_stop_script="\${script_dir}/\${node_folder}/stop.sh"

  if [ -f "\$node_stop_script" ]; then
    echo "-----------------------------"
    echo "停止节点：\${node_folder}"
    bash "\$node_stop_script"
  else
    echo "-----------------------------"
    echo "【错误】未检测到节点\${i}的停止脚本: \$node_stop_script"
    echo "节点\${i} 停止失败！"
  fi
done

echo "所有节点停止命令已执行完毕。"
EOF
chmod +x "${OUTPUT_DIR}/stop_all.sh"

echo "一键停止脚本：${OUTPUT_DIR}/stop_all.sh"

echo "所有节点已生成完毕。"