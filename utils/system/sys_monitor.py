import psutil


def get_storage_info():
    all_used = 0
    all_space = 0
    # 获取虚拟内存信息
    disks = psutil.disk_partitions()
    for disk in disks:
        disk_info = psutil.disk_usage(disk.mountpoint)
        all_space += disk_info.total
        all_used += disk_info.used

    return all_used, all_space
