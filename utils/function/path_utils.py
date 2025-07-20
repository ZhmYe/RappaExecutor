import os

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