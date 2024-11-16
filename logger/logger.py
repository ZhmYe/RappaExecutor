import logging
import os
from datetime import datetime


class LogWriter:
    def __init__(self, log_path):
        self.log_path = log_path
        self.logger = self.setup_logger()

    # 配置全局 logger
    def setup_logger(self):
        # 创建 logger 对象
        logger = logging.getLogger("global_logger")
        logger.setLevel(logging.DEBUG)  # 设置最低日志级别

        # 创建控制台输出的 Handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)

        # 创建文件输出的 Handler
        current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_file = os.path.join(self.log_path, f"{current_time}.log")
        file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        file_handler.setLevel(logging.INFO)

        # 定义日志格式
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s", "%Y-%m-%d %H:%M:%S"
        )
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)

        # 将 Handler 添加到 logger
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

        return logger
    def write_log(self, level, message):
        """
        记录日志消息

        Args:
            level (str): 日志级别，例如 "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
            message (str): 日志消息
        """
        level = level.upper()
        if level == "DEBUG":
            self.logger.debug(message)
        elif level == "INFO":
            self.logger.info(message)
        elif level == "WARNING":
            self.logger.warning(message)
        elif level == "ERROR":
            self.logger.error(message)
        elif level == "CRITICAL":
            self.logger.critical(message)
        else:
            raise ValueError(f"Unsupported log level: {level}")
# 初始化全局 logger
logWriter = LogWriter("/root/zkml_test/BHExecutionNode/logs")

