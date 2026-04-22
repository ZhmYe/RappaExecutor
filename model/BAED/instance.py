import pickle
import torch
from model.BAED.datasets.data import get_data
from model.BAED.model import get_model
from paradigm.model import ModelArgs, ModelFormatOutput, ModelEnum
import torch_geometric as pyg
import networkx as nx
from logger.logger import logWriter as log

class BAED_MODEL_INSTANCE:
    def __init__(self, model_args: ModelArgs):
        self.name = ModelEnum.BAED.name
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
        
        # 模仿 generateData.py 的逻辑，进行分批合成
        batch_size = 128
        total_generated_nxgraphs = []
        
        remaining = num_samples
        while remaining > 0:
            current_batch_size = min(remaining, batch_size)
            sampled_pygraph = self.model.sample(current_batch_size, embedding=None)
            pyg_datas = sampled_pygraph.to_data_list()
            
            for pyg_data in pyg_datas:
                feature_keys = [key for key in pyg_data.keys() if key.startswith('feature')]
                feature_keys.append("label")
                
                g_gen = pyg.utils.to_networkx(pyg_data, to_undirected=True)
                
                # 将属性添加到 NetworkX 图的节点属性中
                for i, node in enumerate(g_gen.nodes()):
                    for key in feature_keys:
                        g_gen.nodes[node][key] = pyg_data[key][i]
                        
                largest_cc = max(nx.connected_components(g_gen), key=len)
                g_gen = g_gen.subgraph(largest_cc)
                total_generated_nxgraphs.append(g_gen)
            
            remaining -= current_batch_size
            log.write_log("MODEL", f"Batch generated: {len(total_generated_nxgraphs)}/{num_samples}")

        return ModelFormatOutput(
            model_name=self.name,
            _input=_input,
            output=total_generated_nxgraphs,
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
            args.dataset = self.model_args.dataset
        return args