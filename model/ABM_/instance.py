import argparse
import pickle

import pandas as pd
import torch

from model.ABM_.simulate_function import create_instance, simulate_market
from paradigm.model import ModelArgs, ModelFormatOutput, ModelEnum
from logger.logger import logWriter as log


class ABM_MODEL_INSTANCE:
    def __init__(self, model_args: ModelArgs):
        self.name = ModelEnum.ABM.name
        self.model_args = model_args
        self.device = self._get_device()
        self.args = self._load_args()
        self.load()

    # # load模型
    # def _load_data(self, file_path):
    #     df = pd.read_csv(file_path)
    #     # 获取"date"、"close"列的数据，并将其转换为列表
    #     prices = df['close'].tolist()
    #     dates = df['date'].tolist()
    #     # 使用卡尔曼滤波计算基本面价值
    #     fundamental_value = calculate_fundamental_value(prices)
    #     return prices, dates, fundamental_value

    def load(self):
        args = self.args
        # initialize the FinDiff synthesizer model
        # with open(self.model_args.checkpoint_path, 'rb') as f:
        #     args.params = pickle.load(f)

        log.write_log("MODEL", "Model successfully loaded from: {}".format(self.model_args.model_path))

    def generate_input(self, params: dict = None):
        return None

    def generate_output(self, num_samples=1, params: dict = None):
        # init samples to be generated
        args = self.args
        _input = self.generate_input()
        df_all = []
        for simulate_step in range(num_samples):
            traders, exchange, market = create_instance(args.params, args.fundamental_value,args.prices)
            # 市场模拟
            _, _, market = simulate_market(traders, exchange, market, self.args.prices, self.args.dates, self.args.trader_type, self.args.params,
                                           num_samples)
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
        with open(self.model_args.checkpoint_path, 'rb') as f:
            params = pickle.load(f)
            # 不需要真实数据。时间戳、基本价值量和开盘价已经在参数文件中
            args.dates = params['timestamps']
            args.fundamental_value = params['fundamental_value']
            args.prices = params['open_price']
            args.params = params

        args.num_samples = 1000
        args.trader_type = ["Fundamental_Trader", "Long_term_Momentum_Trader", "Short_term_Momentum_Trader",
                            "Noise_Trader"]
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
