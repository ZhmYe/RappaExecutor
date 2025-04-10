import time

from model.loader import ModelLoader
import unittest
import os
from utils.function.func import get_project_root, get_model_root


class TestLoader(unittest.TestCase):
    def test_loader(self):
        try:
            model_path = get_model_root()
            print("===========================UNIT TEST LOADER===========================")
            loader = ModelLoader(model_path)
            instance = loader.load("BAED",True )
            start = time.time()
            output = instance.generate_output(1000)
            print(output.format_json())
        except Exception as e:
            raise RuntimeError("Unit Test Loader Failed.") from e
        print("===========================UNIT TEST LOADER END===========================")