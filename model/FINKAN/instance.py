import argparse
import os
import pickle

import numpy as np
import pandas as pd
import torch
from sklearn.preprocessing import LabelEncoder, QuantileTransformer
from torch.utils.data import Dataset, DataLoader, TensorDataset
from model.FINKAN.component import MLPSynthesizer, BaseDiffuser
from paradigm.model import ModelArgs, ModelFormatOutput, ModelEnum
from logger.logger import logWriter as log

class FINKAN_MODEL_INSTANCE:
    def __init__(self, model_args: ModelArgs):
        self.name = ModelEnum.FINKAN.name
        self.model_args = model_args
        self.device = self._get_device()
        self.args = self._load_args()
        self.synthesizer_model = None
        self.diffuser_model = None
        self.load()
    # load模型
    def load(self):

        args = self.args
        # initialize the FinDiff synthesizer model
        synthesizer_model = MLPSynthesizer(
            d_in=args.encoded_dim,
            hidden_layers=args.mlp_layers,
            activation=args.activation,
            n_cat_tokens=args.n_cat_tokens,
            n_cat_emb=args.cat_emb_dim,
            n_classes=pd.Series(args.label).nunique(),
            embedding_learned=False
        )

        # initialize the FinDiff base diffuser model
        self.diffuser_model = BaseDiffuser(
            total_steps=args.diffusion_steps,
            beta_start=args.diffusion_beta_start,
            beta_end=args.diffusion_beta_end,
            scheduler=args.scheduler,
            device=self._get_device()
        )

        checkpoint = torch.load(self.model_args.checkpoint_path, weights_only=False, map_location=torch.device('cpu'))
        # synthesizer_model.eval()  # 设置为评估模式
        synthesizer_model.load_state_dict(checkpoint["state"])

        # synthesizer_model.load_state_dict(torch.load(self.model_args.model_path, weights_only=False, map_location=torch.device('cpu')))
        self.synthesizer_model = synthesizer_model
        if torch.cuda.is_available():
            self.synthesizer_model = self.synthesizer_model.to(args.device)

        log.write_log("MODEL", "Model successfully loaded from: {}".format(self.model_args.model_path))

    def generate_input(self, params: dict = None):
        args = self.args
        num_samples = params["samples"]
        samples = torch.randn((num_samples, args.encoded_dim), device=self._get_device())
        sampled_labels = args.label_torch[torch.randint(0, len(args.label_torch), (num_samples,))].to(self._get_device())

        with torch.no_grad():
            # iterate over diffusion steps
            for diffusion_step in reversed(range(0, args.diffusion_steps)):

                # init diffusion timesteps
                timesteps = torch.full((num_samples,), diffusion_step, dtype=torch.long, device=self._get_device())

                # run synthesizer model forward pass
                model_out = self.synthesizer_model(x=samples.float(), timesteps=timesteps, label=sampled_labels)

                # run diffuser model forward pass
                samples = self.diffuser_model.p_sample_gauss(model_out, samples, timesteps)



        # split sample into numeric and categorical parts
        samples = samples.detach().cpu().numpy()
        return samples
    def generate_output(self, num_samples=1, params: dict=None):
        # init samples to be generated
        args = self.args
        samples = self.generate_input({"samples": num_samples})

        # with torch.no_grad():
        #     # iterate over diffusion steps
        #     for diffusion_step in reversed(range(0, args.diffusion_steps)):
        #
        #         # init diffusion timesteps
        #         timesteps = torch.full((len(args.label_torch),), diffusion_step, dtype=torch.long, device=self._get_device())
        #
        #         # run synthesizer model forward pass
        #         model_out = self.synthesizer_model(x=samples.float(), timesteps=timesteps, label=args.label_torch.to(self._get_device()))
        #
        #         # run diffuser model forward pass
        #         samples = self.diffuser_model.p_sample_gauss(model_out, samples, timesteps)



        # split sample into numeric and categorical parts
        # samples = samples.detach().cpu().numpy()
        samples_num = samples[:, args.cat_dim:]
        samples_cat = samples[:, :args.cat_dim]
        # denormalize numeric attributes
        z_norm_upscaled = args.num_scaler.inverse_transform(samples_num)
        z_norm_df = pd.DataFrame(z_norm_upscaled, columns=args.num_attrs)

        # get embedding lookup matrix
        embedding_lookup = self.synthesizer_model.get_embeddings().cpu()

        # reshape back to batch_size * n_dim_cat * cat_emb_dim
        samples_cat = samples_cat.reshape(-1, len(args.cat_attrs), args.cat_emb_dim)

        # compute pairwise distances
        distances = torch.cdist(x1=embedding_lookup, x2=torch.Tensor(samples_cat))

        # get the closest distance based on the embeddings that belong to a column category
        z_cat_df = pd.DataFrame(index=range(len(samples_cat)), columns=args.cat_attrs)

        nearest_dist_df = pd.DataFrame(index=range(len(samples_cat)), columns=args.cat_attrs)

        # iterate over categorical attributes
        for attr_idx, attr_name in enumerate(args.cat_attrs):

            attr_emb_idx = list(args.vocab_per_attr[attr_name])
            attr_distances = distances[:, attr_emb_idx, attr_idx]

            nearest_values, nearest_idx = torch.min(attr_distances, dim=1)
            nearest_idx = nearest_idx.cpu().numpy()

            z_cat_df[attr_name] = np.array(attr_emb_idx)[nearest_idx]  # need to map emb indices back to column indices
            nearest_dist_df[attr_name] = nearest_values.cpu().numpy()

        z_cat_df = z_cat_df.apply(args.label_encoder.inverse_transform)

        samples_decoded = pd.concat([z_cat_df, z_norm_df], axis=1)

        # print(len(samples_decoded))
        # print("generated_nxgraphs:",generated_nxgraphs)
        return ModelFormatOutput(
            model_name=self.name,
            _input=samples,
            output=samples_decoded,
            params=params
        )


    def _get_device(self):
        if self.model_args.is_cuda:
            return torch.device("cuda:0")
        else:
            return torch.device("cpu")
    def _load_args(self):
        args = argparse.Namespace()
        args.seed = 1234
        args.cat_emb_dim = 2
        args.mlp_layers = [1024, 1024, 1024, 1024]
        args.activation = 'lrelu'
        args.diffusion_steps = 1 # 太慢了，这里原本是500 TODO
        args.diffusion_beta_start = 1e-4
        args.diffusion_beta_end = 0.02
        args.scheduler = 'linear'
        train_raw = pd.read_excel(os.path.join(self.model_args.args_path, "{}.xls".format(self.model_args.dataset)), skiprows=[0])

        # determine categorical attributes
        cat_attrs = ['SEX', 'EDUCATION', 'MARRIAGE', 'AGE', 'PAY0', 'PAY2', 'PAY3', 'PAY4', 'PAY5', 'PAY6']
        args.cat_attrs = cat_attrs
        # determine numerical attributes
        num_attrs = ['LIMITBAL', 'BILLAMT1', 'BILLAMT2', 'BILLAMT3', 'BILLAMT4', 'BILLAMT5', 'BILLAMT6',
                     'PAYAMT1', 'PAYAMT2', 'PAYAMT3', 'PAYAMT4', 'PAYAMT5', 'PAYAMT6']

        args.num_attrs = num_attrs
        # remove underscore in column names for correct inverse decoding
        train_raw.columns = [col.replace('_', '') for col in train_raw.columns]

        # convert categorical attributes to string
        train_raw[cat_attrs] = train_raw[cat_attrs].astype(str)

        # iterate over categorical attributes
        for cat_attr in cat_attrs:

            # add col name to every categorical entry to make them distinguishable for embedding
            train_raw[cat_attr] = cat_attr + '_' + train_raw[cat_attr].astype('str')

        # extract label
        args.label = train_raw['default payment next month']
        # merge selected categorical and numerical attributes
        train = train_raw[[*cat_attrs, *num_attrs]]

        # init the quantile transformation
        num_scaler = QuantileTransformer(output_distribution='normal', random_state=args.seed)

        # fit transformation to numerical attributes
        num_scaler.fit(train[num_attrs])
        args.num_scaler = num_scaler
        # transform numerical attributes
        train_num_scaled = num_scaler.transform(train[num_attrs])
        # get vocabulary of categorical attributes
        vocabulary_classes = np.unique(train[cat_attrs])

        # init categorical attribute encoder
        label_encoder = LabelEncoder()

        # fit encoder to categorical attributes
        label_encoder.fit(vocabulary_classes)
        args.label_encoder = label_encoder
        # transform categorical attributes
        train_cat_scaled = train[cat_attrs].apply(label_encoder.transform)

        # collect unique values of each categorical attribute
        vocab_per_attr = {cat_attr: set(train_cat_scaled[cat_attr]) for cat_attr in cat_attrs}
        args.vocab_per_attr = vocab_per_attr

        # convert label
        args.label_torch = torch.LongTensor(args.label)


        # determine number unique categorical tokens
        args.n_cat_tokens = len(np.unique(train[cat_attrs]))

        # determine total categorical embedding dimension
        args.cat_dim = args.cat_emb_dim * len(cat_attrs)

        # determine total numerical embedding dimension
        num_dim = len(num_attrs)

        # determine total embedding dimension
        args.encoded_dim = args.cat_dim + num_dim

        args.device = 'cuda:0' if self.model_args.is_cuda else 'cpu'
        args.model_path = self.model_args.model_root
        return args