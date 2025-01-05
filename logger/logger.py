import logging
import os
from datetime import datetime
from utils.function.func import  get_project_root
from config.config import BHExecutionNodeGlobalConfig
from pathlib import Path


class LogColors:
    RESET = "\033[0m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BLACK = "\033[30m"  # 黑色
    BRIGHT_RED = "\033[1;31m"  # 明亮红色
    BRIGHT_GREEN = "\033[1;32m"  # 明亮绿色
    BRIGHT_YELLOW = "\033[1;33m"  # 明亮黄色
    BRIGHT_BLUE = "\033[1;34m"  # 明亮蓝色
    BRIGHT_MAGENTA = "\033[1;35m"  # 明亮品红
    BRIGHT_CYAN = "\033[1;36m"  # 明亮青色
    BRIGHT_WHITE = "\033[1;37m"  # 明亮白色
    LIGHT_BLACK = "\033[90m"  # 灰色（亮黑色）
    LIGHT_RED = "\033[91m"  # 浅红色
    LIGHT_GREEN = "\033[92m"  # 浅绿色
    LIGHT_YELLOW = "\033[93m"  # 浅黄色
    LIGHT_BLUE = "\033[94m"  # 浅蓝色
    LIGHT_MAGENTA = "\033[95m"  # 浅品红
    LIGHT_CYAN = "\033[96m"  # 浅青色
    LIGHT_WHITE = "\033[97m"  # 浅白色



class ColoredFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": LogColors.WHITE,
        "INFO": LogColors.GREEN,
        "WARNING": LogColors.YELLOW,
        "ERROR": LogColors.RED,
        "STORAGE": LogColors.MAGENTA,
        "NETWORK": LogColors.CYAN,
        "EXECUTION": LogColors.BLUE,
        "MODEL": LogColors.BRIGHT_MAGENTA,
    }

    def format(self, record):
        level_color = self.COLORS.get(record.levelname, LogColors.WHITE)
        message = super().format(record)
        return f"{level_color}{message}{LogColors.RESET}"


class LogWriter:
    NETWORK_LEVEL_NUM = 25
    EXECUTION_LEVEL_NUM = 26
    STORAGE_LEVEL_NUM = 27
    MODEL_LEVEL_NUM = 28

    def __init__(self):
        self.log_path =  Path(get_project_root()) / BHExecutionNodeGlobalConfig.LOG_PATH
        self.debug = False
        self.logger = None

    def init(self):
        # # 如果日志目录不存在，创建目录
        if not self.log_path.exists():
            self.log_path.mkdir(parents=True, exist_ok=True)  # 创建目录（包括父目录）
            
        self.debug = BHExecutionNodeGlobalConfig.DEBUG
        self.logger = self.setup_logger()

    def setup_logger(self):
        logger = logging.getLogger("BHExecutionNode")
        logger.setLevel(logging.DEBUG)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)

        color_formatter = ColoredFormatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s", "%Y-%m-%d %H:%M:%S"
        )
        console_handler.setFormatter(color_formatter)
        logger.addHandler(console_handler)

        if not self.debug:
            current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            log_file = os.path.join(self.log_path, f"{current_time}.log")
            file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
            file_handler.setLevel(logging.INFO)

            file_formatter = logging.Formatter(
                "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s", "%Y-%m-%d %H:%M:%S"
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)

        logging.addLevelName(self.NETWORK_LEVEL_NUM, "NETWORK")
        logging.addLevelName(self.EXECUTION_LEVEL_NUM, "EXECUTION")
        logging.addLevelName(self.STORAGE_LEVEL_NUM, "STORAGE")
        logging.addLevelName(self.MODEL_LEVEL_NUM, "MODEL")

        def network(message, *args, **kwargs):
            if logger.isEnabledFor(self.NETWORK_LEVEL_NUM):
                logger._log(self.NETWORK_LEVEL_NUM, message, args, **kwargs)

        def storage(message, *args, **kwargs):
            if logger.isEnabledFor(self.STORAGE_LEVEL_NUM):
                logger._log(self.STORAGE_LEVEL_NUM, message, args, **kwargs)

        def execution(message, *args, **kwargs):
            if logger.isEnabledFor(self.EXECUTION_LEVEL_NUM):
                logger._log(self.EXECUTION_LEVEL_NUM, message, args, **kwargs)
        def model(message, *args, **kwargs):
            if logger.isEnabledFor(self.MODEL_LEVEL_NUM):
                logger._log(self.EXECUTION_LEVEL_NUM, message, args, **kwargs)

        logger.network = network
        logger.execution = execution
        logger.storage = storage
        logger.model = model
        return logger

    def write_log(self, level, message):
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
        elif level == "NETWORK":
            self.logger.network(message)
        elif level == "EXECUTION":
            self.logger.execution(message)
        elif level == "STORAGE":
            self.logger.storage(message)
        elif level == "MODEL":
            self.logger.model(message)
        else:
            raise ValueError(f"Unsupported log level: {level}")

logWriter = LogWriter()
