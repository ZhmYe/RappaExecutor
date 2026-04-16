import torch

from logger.logger import logWriter as log
from model.ABM.runner import ABMV2PipelineRunner
from paradigm.model import ModelArgs, ModelEnum, ModelFormatOutput


class ABM_V2_MODEL_INSTANCE:
    def __init__(self, model_args: ModelArgs):
        self.name = ModelEnum.ABM_V2.name
        self.model_args = model_args
        self.device = self._get_device()
        self.runner = ABMV2PipelineRunner()
        self.load()

    def load(self):
        log.write_log("MODEL", f"ABM_V2 runner ready from: {self.model_args.model_path}")

    def generate_input(self, params: dict = None):
        return params

    def generate_output(self, num_samples=1, params: dict = None):
        manifest_df = self.runner.run(params or {}, output_size=num_samples)
        return ModelFormatOutput(
            model_name=self.name,
            _input=self.generate_input(params),
            output=manifest_df,
            params=params,
        )

    def _get_device(self):
        if self.model_args.is_cuda:
            return torch.device("cuda:0")
        return torch.device("cpu")
