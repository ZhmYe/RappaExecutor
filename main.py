import argparse
import os
# from uni_test.test_loader import test_loader
from config.config import BHExecutionNodeGlobalConfig


def parse_args():
    """
    解析命令行参数
    """
    parser = argparse.ArgumentParser(description="BHExecutionNode Configuration")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode. Logs will not be saved to files."
    )
    return parser.parse_args()

if __name__ == '__main__':
    # 解析命令行参数
    args = parse_args()

    # 根据命令行参数设置全局调试模式
    BHExecutionNodeGlobalConfig.set_debug(args.debug)
