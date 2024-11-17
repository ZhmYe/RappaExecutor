import os
from uni_test.test_loader import test_loader 
if __name__ == '__main__':
    project_root = os.path.abspath(os.path.dirname(__file__))
    model_path = os.path.join(project_root, 'model')
    test_loader(model_path)

