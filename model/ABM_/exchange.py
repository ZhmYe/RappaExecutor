from model.ABM_.order import Order

class Exchange:

    def __init__(self):
        self.orders = []  # 所有订单的列表
        self.order_id = 1   # 订单的全局唯一标识，初始值为1

    def add_order(self, order):
        # 给订单标识赋值
        order.order_id = self.order_id
        self.order_id += 1

        self.orders.append(order)
        # 订单排序
        self.orders.sort(key=lambda x: (
            not x.is_buy,   # 买单在前，卖单在后
            -x.price if x.is_buy else x.price,  # 买单按价格降序，卖单按价格升序
            x.timestamp   # 相同价格的订单按时间戳升序
            ), reverse=False)
        
        # 把订单标识返回给交易者
        return order.order_id
    
    # 通过标识查找订单
    def find_order(self, order_id):
        order = [o for o in self.orders if o.order_id == order_id]
        return order[0]
    
    # 通过标识删除订单
    def del_order(self, order_id):
        order = [o for o in self.orders if o.order_id == order_id]
        # 如果找到了订单，删除该订单
        if len(order) > 0:
            self.orders.remove(order[0])

    # 计算中心价
    def calculate_midprice(self):
        buy_orders = [o for o in self.orders if o.is_buy]
        sell_orders = [o for o in self.orders if not o.is_buy]

        # 如果订单簿中数据不足以计算中心价，返回None
        if len(buy_orders) == 0 or len(sell_orders) == 0:
            return None
        
        buy = buy_orders[0]     # 取最高价买单
        sell = sell_orders[0]   # 取最低价卖单
        mid_price = round((buy.price + sell.price) / 2, 2)

        return mid_price


    # 撮合市价订单（及时成交剩余撤销）
    def add_and_match_market_order(self, order):
        # 如果是限价单,报错
        if order.order_type == 0:
            print("错误，该订单不是市价单")
            return None
        else:
            matched_orders = []

            # 如果市价单为买单
            if order.is_buy:
                sell_orders = [o for o in self.orders if not o.is_buy]
                while order.quantity > 0 and sell_orders:
                    sell = sell_orders[0]
                    quantity = min(order.quantity, sell.quantity)
                    # 创建新的订单实例来记录成交信息
                    matched_buy = Order(order.trader_id, order.order_type, order.stock_symbol, order.price, order.quantity, order.is_buy, order.timestamp, order.order_id)
                    matched_sell = Order(sell.trader_id, sell.order_type, sell.stock_symbol, sell.price, sell.quantity, sell.is_buy, sell.timestamp, sell.order_id)
                    matched_orders.append((matched_buy, matched_sell, quantity, sell.price))
                    # 更新交易后订单信息，如果订单数量为0，清空该订单
                    order.quantity -= quantity
                    sell.quantity -= quantity

                    if sell.quantity == 0:
                        sell_orders.pop(0)
                        self.orders.pop(self.orders.index(sell))
            
            else:
                buy_orders = [o for o in self.orders if o.is_buy]
                while order.quantity > 0 and buy_orders:
                    buy = buy_orders[0]
                    quantity = min(order.quantity, buy.quantity)
                    # 创建新的订单实例来记录成交信息
                    matched_buy = Order(buy.trader_id, buy.order_type, buy.stock_symbol, buy.price, buy.quantity, buy.is_buy, buy.timestamp, buy.order_id)
                    matched_sell = Order(order.trader_id, order.order_type, order.stock_symbol, order.price, order.quantity, order.is_buy, order.timestamp, order.order_id)
                    matched_orders.append((matched_buy, matched_sell, quantity, buy.price))
                    # 更新交易后订单信息，如果订单数量为0，清空该订单
                    order.quantity -= quantity
                    buy.quantity -= quantity

                    if buy.quantity == 0:
                        buy_orders.pop(0)
                        self.orders.pop(self.orders.index(buy))
            
            return matched_orders

    # 匹配订单, 计算价格 (集合竞价)   
    def match_orders_in_call_auction(self):
        matched_orders = []
        buy_orders = [o for o in self.orders if o.is_buy]
        sell_orders = [o for o in self.orders if not o.is_buy]
        while buy_orders and sell_orders:
            buy = buy_orders[0]     # 取最高价买单
            sell = sell_orders[0]   # 取最低价卖单
            if buy.price >= sell.price:
                # 计算成交的货品数量
                quantity = min(buy.quantity, sell.quantity)
                # 创建新的订单实例来记录成交信息
                matched_buy = Order(buy.trader_id, buy.order_type, buy.stock_symbol, buy.price, buy.quantity, buy.is_buy, buy.timestamp, buy.order_id)
                matched_sell = Order(sell.trader_id, sell.order_type, sell.stock_symbol, sell.price, sell.quantity, sell.is_buy, sell.timestamp, sell.order_id)
                matched_orders.append((matched_buy, matched_sell, quantity))
                # 更新交易后订单信息，如果订单数量为0，清空该订单
                buy.quantity -= quantity
                sell.quantity -= quantity

                if buy.quantity == 0:
                    buy_orders.pop(0)
                    self.orders.pop(self.orders.index(buy))
                    
                if sell.quantity == 0:
                    sell_orders.pop(0)
                    self.orders.pop(self.orders.index(sell))
                    
            else:
                break
        # 计算集合竞价市场价格（最后一笔成交价）
        if len(matched_orders) > 0:
            mean_price = round((matched_orders[-1][0].price + matched_orders[-1][1].price) / 2, 2)
        else:
            mean_price = None
        
        # 将市场价格补充到每个match_order末尾，对齐元组大小
        new_matched_orders = [o + (mean_price,) for o in matched_orders]

        return new_matched_orders, mean_price

    # 匹配订单, 计算价格 (连续竞价) 
    def match_orders_in_continuous_auction(self):
        matched_orders = []
        buy_orders = [o for o in self.orders if o.is_buy]
        sell_orders = [o for o in self.orders if not o.is_buy]
        while buy_orders and sell_orders:
            buy = buy_orders[0]     # 取最高价买单
            sell = sell_orders[0]   # 取最低价卖单
            if buy.price >= sell.price:
                # 计算成交的货品数量
                quantity = min(buy.quantity, sell.quantity)
                # 计算成交价格
                mean_price = round((buy.price + sell.price) / 2, 2) #保留两位小数
                # 创建新的订单实例来记录成交信息
                matched_buy = Order(buy.trader_id, buy.order_type, buy.stock_symbol, buy.price, buy.quantity, buy.is_buy, buy.timestamp, buy.order_id)
                matched_sell = Order(sell.trader_id, sell.order_type, sell.stock_symbol, sell.price, sell.quantity, sell.is_buy, sell.timestamp, sell.order_id)
                matched_orders.append((matched_buy, matched_sell, quantity, mean_price))
                # 更新交易后订单信息，如果订单数量为0，清空该订单
                buy.quantity -= quantity
                sell.quantity -= quantity

                if buy.quantity == 0:
                    buy_orders.pop(0)
                    self.orders.pop(self.orders.index(buy))
                    
                if sell.quantity == 0:
                    sell_orders.pop(0)
                    self.orders.pop(self.orders.index(sell))
                    
            else:
                break
        
        return matched_orders
    

    '''# ----------- 处理当前交易所订单簿为市场行情 -------------- 
    def order_book_to_market(self, mid_price, range_num, price_range):
        """
        :param mid_price: 当前的市场中心价
        :param range_num: 行情档位数量
        :param price_range: 行情档位之间的价格间隔
        :return: 当前市场行情
        """
        # 将订单簿划分成卖单和卖单（交易所当前时刻的订单簿是有序的，买单按价格降序，卖单按价格升序）
        buy_orders = [o for o in self.orders if o.is_buy]
        sell_orders = [o for o in self.orders if not o.is_buy]

        # 计算买卖的档位价格（买价格从中心价递减，卖价格从中心价递增）
        buy_prices = [mid_price - price_range * (i + 1) for i in range(range_num)]
        buy_prices = [round(price, 2) for price in buy_prices]
        sell_prices = [mid_price + price_range * (i + 1) for i in range(range_num)]
        sell_prices = [round(price, 2) for price in sell_prices]


        # -------统计买方档位价格对应的存量-------
        buy_volumes = []
        range_count = 0
        volume = 0
        for order in buy_orders:
            if order.price >= buy_prices[range_count]:
                volume += order.quantity
            # 进入下一档，保存上一档数据，重置存量
            else:
                buy_volumes.append(volume)
                volume = 0
                range_count += 1
                # 最后一档，其余订单不统计
                if range_count >= range_num:
                    break
        # 不足五档，存量补0
        if len(buy_volumes) < range_num:
            for i in range(len(buy_volumes), range_num):
                buy_volumes.append(0)

        # ------统计卖方档位价格对应的存量---------
        sell_volumes = []
        range_count = 0
        volume = 0
        for order in sell_orders:
            if order.price <= sell_prices[range_count]:
                volume += order.quantity
            # 进入下一档，保存上一档数据，重置存量      
            else:
                sell_volumes.append(volume)
                volume = 0
                range_count += 1
                # 最后一档，其余订单不统计
                if range_count >= range_num:
                    break
        # 不足五档，存量补0
        if len(sell_volumes) < range_num:
            for i in range(len(sell_volumes), range_num):
                sell_volumes.append(0)

        # 将档位价格和存量集中成当前市场行情(buy1,sell1,bc1,sc1...)
        market_situations = []
        for i in range(range_num):
            market_situations.append(buy_prices[i])
            market_situations.append(sell_prices[i])
            market_situations.append(buy_volumes[i])
            market_situations.append(sell_volumes[i])

        return market_situations'''
    
    # ----------- 处理当前交易所订单簿为市场十档行情 -------------- 
    def order_book_to_market(self, mid_price, range_num, price_range):
        """
        :param mid_price: 当前的市场中心价
        :param range_num: 行情档位数量
        :param price_range: 最小价格变动单位
        :return: 当前市场行情
        """
        # 将订单簿划分成卖单和卖单（交易所当前时刻的订单簿是有序的，买单按价格降序，卖单按价格升序）
        buy_orders = [o for o in self.orders if o.is_buy]
        sell_orders = [o for o in self.orders if not o.is_buy]

        # 处理买方向档位
        buy_prices = []
        buy_volumes = []
        # 如果买方向为空，以当前的市场中心价为基准，按最小价格变动单位向下递减生成档位价格
        if not buy_orders:
            buy_prices = [round(mid_price - price_range * (i + 1), 2) for i in range(range_num)]
            buy_volumes = [0 for i in range(range_num)]
        # 如果买方向不为空，按顺序取订单的不同价格作为档位，并计算存量，不足十档按最小价格变动单位向下递减生成档位价格
        else:
            for i in range(len(buy_orders)):
                # 如果是第一个价格，添加新档位价格和存量
                if i == 0:
                    buy_prices.append(buy_orders[i].price)
                    buy_volumes.append(buy_orders[i].quantity)
                # 如果当前订单的价格与最新档位的价格不同，添加新档位价格和存量
                elif buy_orders[i].price != buy_prices[-1]:
                    # 如果此时已经有足够档位价格，退出循环
                    if len(buy_prices) >= range_num:
                        break
                    else:
                        buy_prices.append(buy_orders[i].price)
                        buy_volumes.append(buy_orders[i].quantity)
                # 如果当前订单的价格与最新档位的价格相同，补充最新档位存量
                else:
                    buy_volumes[-1] += buy_orders[i].quantity
            # 处理完买方向订单后，档位价格依旧不足，补充档位
            if len(buy_prices) < range_num:
                for i in range(range_num - len(buy_prices)):
                    buy_prices.append(round(buy_prices[-1] - price_range, 2))
                    buy_volumes.append(0)

        # 处理卖方向档位
        sell_prices = []
        sell_volumes = []
        # 如果卖方向为空，以当前的市场中心价为基准，按最小价格变动单位向上递增生成档位价格
        if not sell_orders:
            sell_prices = [round(mid_price + price_range * (i + 1), 2) for i in range(range_num)]
            sell_volumes = [0 for i in range(range_num)]
        # 如果卖方向不为空，按顺序取订单的不同价格作为档位，并计算存量，不足十档按最小价格变动单位向上递增生成档位价格
        else:
            for i in range(len(sell_orders)):
                # 如果是第一个价格，添加新档位价格和存量
                if i == 0:
                    sell_prices.append(sell_orders[i].price)
                    sell_volumes.append(sell_orders[i].quantity)
                # 如果当前订单的价格与最新档位的价格不同，添加新档位价格和存量
                elif sell_orders[i].price != sell_prices[-1]:
                    # 如果此时已经有足够档位价格，退出循环
                    if len(sell_prices) >= range_num:
                        break
                    else:
                        sell_prices.append(sell_orders[i].price)
                        sell_volumes.append(sell_orders[i].quantity)
                # 如果当前订单的价格与最新档位的价格相同，补充最新档位存量
                else:
                    sell_volumes[-1] += sell_orders[i].quantity
            # 处理完卖方向订单后，档位价格依旧不足，补充档位
            if len(sell_prices) < range_num:
                for i in range(range_num - len(sell_prices)):
                    sell_prices.append(round(sell_prices[-1] + price_range, 2))
                    sell_volumes.append(0)
        
        # 将档位价格和存量集中成当前市场行情(buy1,sell1,bc1,sc1...)
        market_situations = []
        for i in range(range_num):
            market_situations.append(buy_prices[i])
            market_situations.append(sell_prices[i])
            market_situations.append(buy_volumes[i])
            market_situations.append(sell_volumes[i])

        return market_situations

    
    # 计算市场累计价差分布(上限10个价差之和)
    def order_book_to_spread(self):
        # 将订单簿划分成卖单和卖单（交易所当前时刻的订单簿是有序的，买单按价格降序，卖单按价格升序）
        buy_orders = [o for o in self.orders if o.is_buy]
        sell_orders = [o for o in self.orders if not o.is_buy]

        spread = 0
        count = 0
        order_len = min(len(buy_orders), len(sell_orders))
        # 十档累积价差
        while count < order_len and count < 10:
            spread += sell_orders[count].price - buy_orders[count].price
            count += 1
        
        return spread




# Example:
'''exchange = Exchange()
exchange.add_order(Order(1, '0001', 3.80, 2, True, 1))
exchange.add_order(Order(1, '0001', 3.76, 6, True, 2))
exchange.add_order(Order(1, '0001', 3.60, 7, True, 4))
exchange.add_order(Order(2, '0001', 3.52, 5, False, 1))
exchange.add_order(Order(2, '0001', 3.57, 1, False, 3))
exchange.add_order(Order(3, '0001', 3.54, 6, False, 3))
exchange.add_order(Order(1, '0001', 3.60, 2, True, 3))
exchange.add_order(Order(2, '0001', 3.70, 6, False, 2))
exchange.add_order(Order(3, '0001', 3.75, 3, False, 4))
exchange.add_order(Order(1, '0001', 3.65, 4, True, 3))

for order in exchange.orders:
    print(order)

# match_orders, mean_price = exchange.match_orders_in_call_auction()
match_orders = exchange.match_orders_in_continuous_auction()
for order in match_orders:
    print(order)
    print(order[3])
# print("-----------")
# print("集合竞价平均价格：",mean_price)'''