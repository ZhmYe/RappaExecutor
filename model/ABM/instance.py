import argparse
import os
import pickle

import numpy as np
import pandas as pd
import torch
from pandas import DataFrame

from model.ABM.func import calculate_fundamental_value, create_instance, simulate_market
from paradigm.model import ModelArgs, ModelFormatOutput, ModelEnum
from logger.logger import logWriter as log


class ABM_MODEL_INSTANCE:
    def __init__(self, model_args: ModelArgs):
        self.name = ModelEnum.ABM.name
        self.model_args = model_args
        self.device = self._get_device()
        self.args = self._load_args()
        self.traders = None
        self.exchange = None
        self.market = None
        self.load()

    # load模型
    def _load_data(self, file_path):
        df = pd.read_csv(file_path)
        # 获取"date"、"close"列的数据，并将其转换为列表
        prices = df['close'].tolist()
        dates = df['date'].tolist()
        # 使用卡尔曼滤波计算基本面价值
        fundamental_value = calculate_fundamental_value(prices)
        return prices, dates, fundamental_value

    def load(self):

        args = self.args
        # initialize the FinDiff synthesizer model
        with open(self.model_args.checkpoint_path, 'rb') as f:
            args.params = pickle.load(f)

        self.traders, self.exchange, self.market = create_instance(args.params, args.fundamental_value, args.prices[0])

        log.write_log("MODEL", "Model successfully loaded from: {}".format(self.model_args.model_path))

    def generate_input(self, params: dict = None):
        return None

    def generate_output(self, num_samples=1, params: dict = None):
        # init samples to be generated
        args = self.args
        _input = self.generate_input()
        _, _, market = simulate_market(self.traders, self.exchange, self.market, args.prices, args.dates,
                                       args.trader_type, args.params)

        # 这里的num_samples表示一份数据
        df_all = []
        for i in range(num_samples):
            df_all.append(self._process_data(market))
        dfs = pd.concat(df_all, axis=1)
        # print(len(samples_decoded))
        # print("generated_nxgraphs:",generated_nxgraphs)
        return ModelFormatOutput(
            model_name=self.name,
            _input=None,
            output=dfs,
            params=params
        )

    def _get_device(self):
        if self.model_args.is_cuda:
            return torch.device("cuda:0")
        else:
            return torch.device("cpu")

    def _load_args(self):
        args = argparse.Namespace()
        args.trader_type = ["Fundamental_Trader", "Long_term_Momentum_Trader", "Short_term_Momentum_Trader",
                            "Noise_Trader"]
        args.prices, args.dates, args.fundamental_value = self._load_data(
            os.path.join(self.model_args.args_path, "{}.csv".format(self.model_args.dataset)))

        return args

    def _process_data(self, market):
        data = []

        for i in range(len(market.orders)):
            data.append({
                "Timestamp": market.orders[i][0],
                "Orders": market.orders[i][1],
                "MatchResult": market.match_result[i][1],
                "MeanPrice": market.price_trend[i][1],
                "MidPrice": market.mid_price[i][1],
                "MultipleMarket": market.multiple_market[i][1],
            })

        df = pd.DataFrame(data)

        # 按时间戳排序
        df.sort_values(by="Timestamp", inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df
