from logger.logger import logWriter as log

class BHExecutionNodeGlobalConfig:
    debug = False  # 全局调试模式，默认关闭

    @staticmethod
    def set_debug(value: bool):
        BHExecutionNodeGlobalConfig.debug = value
        log.init(value)
    @staticmethod
    def get_debug() -> bool:
        return BHExecutionNodeGlobalConfig.debug
