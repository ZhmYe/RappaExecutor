from model.loader import ModelLoader
def test_loader(model_path):
    loader = ModelLoader(model_path)
    instance = loader.load("ctgan", "ctgan_model.pth")
    output = instance.generate_output(1000)
    print(output.format_json())