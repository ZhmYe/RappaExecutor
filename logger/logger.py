import logging
import os
from datetime import datetime


class LogWriter:
    TRACK_LEVEL_NUM = 25  # 自定义日志级别，介于 INFO 和 WARNING 之间

    def __init__(self, log_path):
        """
        初始化 LogWriter

        Args:
            log_path (str): 日志文件的存储路径。
            debug (bool): 是否处于调试模式（调试模式下只输出到控制台）。
        """
        self.log_path = log_path
        self.debug = True
        self.logger = None
        # self.logger = self.setup_logger()
    def init(self, debug):
        self.debug = debug
        self.logger = self.setup_logger()
    def setup_logger(self):
        # 创建 logger 对象
        logger = logging.getLogger("BHExecutionNode")
        logger.setLevel(logging.DEBUG)  # 设置最低日志级别

        # 创建控制台输出的 Handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)

        # 定义日志格式
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s", "%Y-%m-%d %H:%M:%S"
        )
        console_handler.setFormatter(formatter)

        # 将控制台 Handler 添加到 logger
        logger.addHandler(console_handler)

        # 如果不是调试模式，添加文件输出 Handler
        if not self.debug:
            current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            log_file = os.path.join(self.log_path, f"{current_time}.log")
            file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        # 添加 TRACK 日志级别
        logging.addLevelName(self.TRACK_LEVEL_NUM, "TRACK")

        # 定义 logger 的 TRACK 方法
        def track(message, *args, **kwargs):
            if logger.isEnabledFor(self.TRACK_LEVEL_NUM):
                logger._log(self.TRACK_LEVEL_NUM, message, args, **kwargs)

        logger.track = track
        return logger

    def write_log(self, level, message):
        """
        记录日志消息

        Args:
            level (str): 日志级别，例如 "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "TRACK"
            message (str): 日志消息
        """
        if self.logger is None:
            return
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
        elif level == "TRACK":
            self.logger.track(message)
        else:
            raise ValueError(f"Unsupported log level: {level}")

logWriter = LogWriter("/root/zkml_test/BHExecutionNode/logs")