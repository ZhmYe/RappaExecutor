import psutil

def get_memory_info():
    # 获取虚拟内存信息
    virtual_memory = psutil.virtual_memory()

    # 返回总内存、已使用内存和内存占用率
    total_memory = virtual_memory.total / (1024 ** 3)  # 转换为 GB
    used_memory = virtual_memory.used / (1024 ** 3)  # 转换为 GB
    memory_usage_percent = virtual_memory.percent

    return total_memory, used_memory, memory_usage_percent