# 该脚本用于创建 grpc 代码
python3 -m grpc_tools.protoc -I. --python_out=network/Grpc/service --grpc_python_out=network/Grpc/service services.proto