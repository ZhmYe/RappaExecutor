#!/bin/bash
# 编译并更新 libgo.so 的脚本 

set -e

SOURCE_DIR="/root/rappa/RappaExecutor/signer/source"
OUTPUT_DIR="/root/rappa/RappaExecutor/signer"
DEPLOY_DIR="/root/rappa/RappaExecutor"
OUTPUT_FILE="libgo.so"

cd "$SOURCE_DIR"

go build -o libgo.so -buildmode=c-shared .
cp "$SOURCE_DIR/$OUTPUT_FILE" "$OUTPUT_DIR" 
cp "$SOURCE_DIR/$OUTPUT_FILE" "$DEPLOY_DIR"

ls -lh "$OUTPUT_DIR/$OUTPUT_FILE"
ls -lh "$DEPLOY_DIR/$OUTPUT_FILE"