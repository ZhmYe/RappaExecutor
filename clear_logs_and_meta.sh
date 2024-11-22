#!/bin/bash

# 标记是否清理
clean_logs=false
clean_meta=false

# 解析输入参数
for arg in "$@"; do
    case "$arg" in
        --log)
            clean_logs=true
            ;;
        --meta)
            clean_meta=true
            ;;
        *)
            echo "Invalid argument: $arg"
            echo "Usage: $0 [--log] [--meta]"
            echo "  --log  : Clear logs directory"
            echo "  --meta : Clear meta directory"
            exit 1
            ;;
    esac
done

# 清理 logs 目录
if $clean_logs; then
    echo "Cleaning up logs..."
    rm -rf logs/*
    echo "Logs cleaned."
fi

# 清理 meta 目录
if $clean_meta; then
    echo "Cleaning up meta..."
    rm -rf meta/*
    echo "Meta cleaned."
fi

# 如果没有参数，则提示用法
if ! $clean_logs && ! $clean_meta; then
    echo "Usage: $0 [--log] [--meta]"
    echo "  --log  : Clear logs directory"
    echo "  --meta : Clear meta directory"
fi
