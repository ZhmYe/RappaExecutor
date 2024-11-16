from model.loader import ModelLoader
import os
if __name__ == '__main__':
    project_root = os.path.abspath(os.path.dirname(__file__))
    model_path = os.path.join(project_root, 'model')
    loader = ModelLoader(model_path)
    instance = loader.load("ctgan", "ctgan_model.pth")
    output = instance.generate_output(1000)
    print(output.format())

