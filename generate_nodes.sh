#!/bin/bash

set -e

###############################################################################
# 1. 参数解析
###############################################################################
code_path="$(cd "$(dirname "$0")" && pwd)"  # 获取Executor代码的绝对路径。
NODES_NUM="$1"                             # 第一个参数：节点数量
if [ -z "$NODES_NUM" ]; then
  echo "use: $0 <NODES_NUM> [OUTPUT_DIR]"
  exit 1
fi

OUTPUT_DIR="$2"                            # 第二个参数：输出目录
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
# 3. 为每个节点创建目录结构，复制代码并覆盖 config.json、生成启动脚本
###############################################################################
for (( i=0; i<NODES_NUM; i++ )); do
  node_folder="node${i}"
  # echo "-----------------------------"
  # echo "创建节点目录：$node_folder"
  mkdir -p "$node_folder"

  # 3.1 复制 RappaExecutor 目录到节点目录下
  cp -r "${code_path}" "${node_folder}/"
  
  # 3.2 生成新的 config.json（如果源目录里原本就有 config.json，将被下面操作覆盖）
  cat <<EOF > "${node_folder}/RappaExecutor/config.json"
{
  "NODE_ID": $i,
  "EC_PARAMS_N": 9,
  "EC_PARAMS_K": 6,
  "NODE_IP": "127.0.0.1",
  "GRPC_PORT": $((1234 + i*2)),
  "LAYER2_ADDRESS_IP": "127.0.0.1",
  "LAYER_ADDRESS_PORT": $((1235 + i*2)),
  "STORAGE_PATH": "meta"
}
EOF
  # echo "已生成并覆盖配置文件：${node_folder}/RappaExecutor/config.json"

  # 3.3 创建单个节点的启动脚本 start.sh
  cat <<EOF > "${node_folder}/start.sh"
#!/bin/bash

# 读取第一个参数，判断是否为 --debug
MODE="\$1"

# 切换到 RappaExecutor 目录
cd "\$(dirname "\$0")/RappaExecutor" || exit 1

echo "启动节点：node${i}"

# 根据 MODE 是否为 --debug 执行不同命令
if [ "\$MODE" = "--debug" ]; then
  echo "节点 node${i}：进入调试模式..."
  python main.py --debug
else
  echo "节点 node${i}：进入生产模式..."
  python main.py
fi
EOF
  chmod +x "${node_folder}/start.sh"
  # echo "已生成启动脚本：${node_folder}/start.sh"
done

###############################################################################
# 4. 生成一键启动脚本：start_all.sh
###############################################################################
cat <<EOF > "./start_all.sh"
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
# echo "一键启动脚本：$(pwd)/start_all.sh"
echo "所有节点已生成完毕。"
