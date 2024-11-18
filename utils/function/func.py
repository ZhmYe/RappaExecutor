import os
# 这里放一些可以修改的用户定义的函数，比如路径什么的

def get_project_root():
    """
    Get the root directory of the project by searching for a specific marker file.
    """
    current_dir = os.path.abspath(os.path.dirname(__file__))
    while current_dir != os.path.dirname(current_dir):  # Stop at filesystem root
        if ".project_root" in os.listdir(current_dir):  # Check for marker file
            return current_dir
        current_dir = os.path.dirname(current_dir)
    raise FileNotFoundError("Project root marker file not found.")

def get_model_root():
    project_root = get_project_root()
    return os.path.join(project_root, 'model')

def get_model_params_dict(model_name):
    model_dict = {
        "ctgan": {
            "dir_path": "test",
            "model_name": "ctgan_model.pth",
            "sampler_file_name": "sampler"
        }
    }
    if model_dict.get(model_name) is None:
        raise ValueError("model dict didn't save the model {}, please modify model_dict in utils/function/func.py".format(model_name))
    return model_dict[model_name]