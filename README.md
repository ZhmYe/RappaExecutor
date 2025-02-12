# **BHExecutionNode**

## **项目简介**

BHExecutionNode 是一个合成数据任务处理框架，用于接收 Layer2Node 的数据合成任务。框架通过模型加载和数据生成模块完成任务的分配和处理，支持通过 gRPC 或 HTTP 接收任务请求。模块化设计使框架具备灵活性和可扩展性。

---

## **核心目录结构**

```
BHExecutionNode/
├── config/                # 全局配置模块
├── logger/                # 日志管理模块
├── main.py                # 项目入口
├── model/                 # 模型加载和管理模块
│   ├── ctgan/             # CTGAN 模型具体实现
│   │   ├── instance.py    # CTGAN 模型实例
│   │   └── test/          # 测试模型目录，包含权重文件
│   ├── format.py          # 模型接口标准化
│   └── loader.py          # 模型加载器
├── network/               # 网络传输模块
│   ├── Grpc/              # gRPC 实现
│   │   ├── FakeGrpc.py    # 模拟 gRPC 服务
│   │   └── grpc.py        # 实际 gRPC 服务
│   └── Http/              # HTTP 实现（占位模块）
├── node/                  # 节点核心模块
│   ├── Task/              # 任务管理模块
│   │   ├── processor.py   # 任务处理器
│   │   ├── slot.py        # 任务分片逻辑
│   │   └── task.py        # 任务生命周期管理
│   ├── format.py          # 节点数据格式化工具
│   └── node.py            # 节点核心逻辑
├── storage/               # 数据存储模块（待实现）
├── uni_test/              # 单元测试模块
└── utils/                 # 工具模块
    ├── chunk/             # 数据分块工具
    ├── cryptography/      # 加密相关工具
    │   ├── commitment/    # Merkle 树实现
    │   └── sha256.py      # 哈希算法实现
    ├── ec/                # 纠删码实现
    │   └── RSCode.py      # RS 编码模块
    └── function/          # 通用工具
        └── func.py        # 工具函数
```

---

## **模块说明**

### **1. 核心模块**

#### **1.1 BHExecutionNode**

- **位置**：`node/node.py`
- **功能**：
    - 接收任务，将任务加入队列并通过模型加载器执行。
    - 支持调试模式（`FakeGrpcEngine` 模拟任务生成）和生产模式（实际 gRPC 服务）。
    - 主要组件：
        - `process_task`：从任务池中提取任务并运行分片。
        - `checkpoint`：支持任务状态持久化，方便任务恢复。

#### **1.2 任务管理**

- **位置**：`node/Task/`
- **功能**：
    - `task.py`：
        - 定义任务的生命周期管理，支持任务分片和序列化。
    - `slot.py`：
        - 定义任务分片逻辑，每个分片是独立的任务子单元。
    - `processor.py`：
        - 提供分片的实际处理逻辑，通过模型实例完成数据合成。

---

### **2. 模型模块**

#### **2.1 模型加载与管理**

- **位置**：`model/loader.py`
- **功能**：
    - 根据任务需求动态加载模型。
    - 提供统一的接口以支持多种模型扩展。

#### **2.2 CTGAN 模型**

- **位置**：`model/ctgan/`
- **功能**：
    - 实现 CTGAN 模型实例，支持数据生成及格式化输出。
    - **组件**：
        - `component.py`：定义生成器和残差网络。
        - `instance.py`：提供模型加载和生成接口。
        - `train_model.py`：训练脚本，方便模型的本地训练和验证。
#### **2.3 BAED 模型**

- **位置**：`model/BAED/`
- **功能**：
    - 实现 BAED 模型实例，支持数据生成及格式化输出。
    - **组件**：
        - `instance.py`：提供模型加载和生成接口。
        - 相关权重及其他文件因为隐私问题无法提供
---
#### **2.3 BAED 模型**

- **位置**：`model/BAED/`
- **功能**：
    - 实现 BAED 模型实例，支持数据生成及格式化输出。
    - **组件**：
        - `instance.py`：提供模型加载和生成接口。
        - 相关权重及其他文件因为隐私问题无法提供
---

### **3. 网络模块**

#### **3.1 gRPC**

- **位置**：`network/Grpc/`
- **功能**：
    - `FakeGrpc.py`：
        - 模拟任务生成和分发逻辑，用于调试模式。
    - `grpc.py`：
        - 实现生产环境下的 gRPC 服务，支持任务流式传输。

#### **3.2 HTTP**

- **位置**：`network/Http/`
- **功能**：
    - 提供 HTTP 通信占位实现，便于扩展其他协议支持。

---

### **4. 日志模块**

#### **4.1 日志管理**

- **位置**：`logger/logger.py`
- **功能**：
    - 提供标准日志级别（`DEBUG`、`INFO`、`WARNING` 等）。
    - 支持自定义日志级别 `TRACK`，用于跟踪任务状态。
    - 调试模式下仅输出到控制台，生产模式下支持文件输出。

---

### **5. 工具模块**

#### **5.1 数据分块**

- **位置**：`utils/chunk/chunker.py`
- **功能**：
    - 提供数据分块工具，支持任务数据的切片和组合。

#### **5.2 RS 编码**

- **位置**：`utils/ec/RSCode.py`
- **功能**：
    - 实现数据冗余存储的 Reed-Solomon 编码和解码功能。

#### **5.3 通用工具**

- **位置**：`utils/function/func.py`
- **功能**：
    - 提供项目路径解析、模型参数管理和通用工具函数。

---

## **运行指南**

### **运行环境**

- Python >= 3.8

- 安装依赖：

  ```bash
  pip install -r requirements.txt
  ```

### **启动节点**
### **单节点**
1. 调试模式：

   ```bash
   python main.py --debug
   ```

2. 生产模式：

   ```bash
   python main.py
   ```

### **多节点**

#### 1. 单机部署多节点

- **基本用法：** 第一个参数即为节点数，需要至少指定一个整数节点数量。  

  ```bash
  ./RappaExecutor/generate_nodes.sh 100
  ```
  在当前目录下直接创建 `nodes` 文件夹并生成 100 个节点，生成的节点目录为 `./nodes`，并在该目录下生成一键启动脚本 `start_all.sh`。

- **自定义输出路径：** 如果需要在其他指定路径下创建 `nodes` 目录并生成节点，可以在第二个参数中指定输出路径。
  ```bash
  ./RappaExecutor/generate_nodes.sh 100 output
  ```
  脚本会在 `./output` 目录下创建节点主目录`nodes`。

#### 2. 启动所有节点
- 调试模式

  ```bash
  ./nodes/start_all.sh --debug
  ```
- 生产模式

  ```bash
  ./nodes/start_all.sh
  ```
#### 3. 终止所有节点
- 运行nodes目录下的`stop_all.sh`，调用每个节点目录下的`stop.sh`终止节点对应进程。

  ```bash
  ./nodes/stop_all.sh
  ```
---

## **测试指南**

### **运行所有单元测试**

```bash
python -m unittest discover -s uni_test -p "*.py"
```

#### **单独测试**

1. **任务处理测试**：

   ```bash
   python -m unittest uni_test/test_BHExecutionNode.py
   ```

2. **FakeGrpc 测试**：

   ```bash
   python -m unittest uni_test/test_fake_grpc_engine.py
   ```

3. **模型加载测试**：

   ```bash
   python -m unittest uni_test/test_loader.py
   ```

---

如果还需要调整或补充内容，请随时告知！
