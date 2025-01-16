import pickle
import torch
from model.AGGS.datasets.data import get_data
from model.AGGS.model import get_model
from paradigm.model import ModelArgs, ModelFormatOutput, ModelEnum
import torch_geometric as pyg
import networkx as nx
from logger.logger import logWriter as log

class AGGS_MODEL_INSTANCE:
    def __init__(self, model_args: ModelArgs):
        self.name = ModelEnum.AGGS.name
        self.model_args = model_args
        self.device = self._get_device()
        self.args = self._load_args()
        self.model = None
        self.model = self.load()
    # load模型
    def load(self):
        args = self.args
        # 这里大部分东西似乎用不到
        train_loader, eval_loader, test_loader, num_node_feat, num_node_classes, num_edge_classes, max_degree, augmented_feature_dict, initial_graph_sampler, eval_evaluator, test_evaluator, monitoring_statistics = get_data(args)
        model = get_model(args, initial_graph_sampler=initial_graph_sampler)
        checkpoint = torch.load(self.model_args.checkpoint_path, map_location=self.device)
        model.load_state_dict(checkpoint['model'])
        if torch.cuda.is_available():
            model = model.to(args.device)
        model.eval()
        log.write_log("MODEL", "Model successfully loaded from: {}".format(self.model_args.model_path))
        return model
    def generate_input(self, params: dict = None):
        return None
    def generate_output(self, num_samples=1, params: dict=None):
        _input = self.generate_input()
        sampled_pygraph = self.model.sample(num_samples,embedding=None)
        # print(sampled_pygraph)
        pyg_datas = sampled_pygraph.to_data_list()
        generated_nxgraphs = []

        for pyg_data in pyg_datas:
            g_gen = pyg.utils.to_networkx(pyg_data, to_undirected=True)
            largest_cc = max(nx.connected_components(g_gen), key=len)
            g_gen = g_gen.subgraph(largest_cc)
            generated_nxgraphs.append(g_gen)

        # print("generated_nxgraphs:",generated_nxgraphs)
        return ModelFormatOutput(
            model_name=self.name,
            _input=_input,
            output=generated_nxgraphs,
            params=params
        )


    def _get_device(self):
        if self.model_args.is_cuda:
            return torch.device("cuda:0")
        else:
            return torch.device("cpu")
    def _load_args(self):
        with open(self.model_args.args_path, 'rb') as f:
            args = pickle.load(f)
            args.device = 'cuda:0' if self.model_args.is_cuda else 'cpu'
            args.model_path = self.model_args.model_root
        return args