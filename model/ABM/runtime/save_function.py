import pandas as pd
import numpy as np
import csv

# 保存订单簿数据为可重复使用的格式
def save_order_book(filename, orders):
    # 打开文件用于写入
    with open(filename, mode='w', newline='') as file:
        # 创建csv.writer对象
        writer = csv.writer(file)
        # 写入标题行
        writer.writerow(['Timestamp', 'UserID', 'OrderType', 'StockCode', 'Price', 'Volume', 'IsBuy', 'OrderTimestamp', 'OrderID'])
        
        # 遍历订单簿并写入数据
        for order in orders:
            timestamp = order[0]  # 时间戳
            order_list = order[1]  # Order 列表
            # 遍历order列表，处理单个order数据
            for order_obj in order_list:
                # 将 Order 对象的属性写入 CSV
                writer.writerow([
                    timestamp,
                    order_obj.trader_id,
                    'Limit' if order_obj.order_type == 0 else 'Market',
                    order_obj.stock_symbol,
                    order_obj.price,
                    order_obj.quantity,
                    order_obj.is_buy,
                    order_obj.timestamp,
                    order_obj.order_id
                ])

    print(f'数据已写入 {filename}')