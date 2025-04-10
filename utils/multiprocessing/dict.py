import os
import pickle
from multiprocessing import Manager
from multiprocessing.managers import DictProxy, ListProxy

from logger.logger import logWriter as log


class SuperSharedDict:
    def __init__(self, manager: Manager, location, autosave=False, recover=False):
        """
        初始化数据库

        参数:
            manager (Manager): multiprocessing Manager实例
            location (str): 数据文件路径
            autosave (bool): 是否自动持久化 (默认关闭)
            recover (bool): 是否从文件恢复数据 (默认关闭)
        """
        self.location = os.path.expanduser(location)
        self.autosave = autosave  # 自动保存开关
        self.db = manager.dict()  # 总是创建新的manager字典
        self._load(manager, recover)

    def _convert_manager_objects(self, obj):
        """递归将嵌套的manager.dict和manager.list转换为普通字典和列表"""
        if isinstance(obj, DictProxy):
            # 如果是manager.dict，转换为普通字典并递归处理值
            return {key: self._convert_manager_objects(value) for key, value in obj.items()}
        elif isinstance(obj, ListProxy):
            # 如果是manager.list，转换为普通列表并递归处理元素
            return [self._convert_manager_objects(elem) for elem in obj]
        elif isinstance(obj, dict):
            # 普通字典递归处理值
            return {k: self._convert_manager_objects(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            # 普通列表递归处理元素
            return [self._convert_manager_objects(elem) for elem in obj]
        elif isinstance(obj, tuple):
            # 元组递归处理元素，并保持元组类型
            return tuple(self._convert_manager_objects(elem) for elem in obj)
        else:
            # 其他类型直接返回
            return obj

    def _conditional_save(self):
        """根据autosave配置决定是否自动保存"""
        if self.autosave:
            self.save()

    def set(self, key, value):
        """
        增强版set方法，支持自动保存
        """
        key = str(key) if not isinstance(key, str) else key
        self.db[key] = value
        self._conditional_save()  # 自动保存检查
        return True

    def remove(self, key):
        """
        增强版remove方法，支持自动保存
        """
        key = str(key) if not isinstance(key, str) else key
        if key in self.db:
            del self.db[key]
            self._conditional_save()  # 自动保存检查
            return True
        return False

    def purge(self):
        """
        增强版purge方法，支持自动保存
        """
        for key in list(self.db.keys()):  # Create a list of keys to avoid RuntimeError
            del self.db[key]
        self._conditional_save()  # 自动保存检查
        return True

    def _load(self, manager: Manager, recover):
        """
        从pickle文件加载数据（如果文件存在且非空），
        否则初始化一个空数据库。
        """
        if (recover and os.path.exists(self.location) and
                os.path.getsize(self.location) > 0):
            try:
                with open(self.location, "rb") as f:
                    data = pickle.load(f)
                    # 批量更新manager字典
                    for key, value in data.items():
                        self.db[str(key)] = value
            except Exception as e:
                raise RuntimeError(f"{e}\nload data from {self.location}。")

    def save(self):
        """
        使用原子保存方式将数据库保存到文件。

        注意:
            - 由于manager.dict()是代理对象，我们首先将其转换为普通字典
            - 先写入临时文件，仅在写入成功后才替换原文件，
              确保数据完整性。

        返回:
            bool: 保存成功返回True，失败返回False。
        """
        temp_location = f"{self.location}.tmp"  # 临时文件路径
        try:
            # 创建普通字典副本用于序列化
            serializable_dict = self._convert_manager_objects(self.db)
            with open(temp_location, "wb") as temp_file:
                pickle.dump(serializable_dict, temp_file)
            os.replace(temp_location, self.location)  # 原子替换
            return True
        except Exception as e:
            log.write_log("ERROR", f"save to db failed:{e}")
            return False

    def get(self, key):
        """
        获取与键关联的值。

        参数:
            key (any): 要检索的键。如果不是字符串类型，将被转换为字符串。

        返回:
            any: 与键关联的值，键不存在则返回None。
        """
        key = str(key) if not isinstance(key, str) else key
        return self.db.get(key)

    def all(self):
        """
        获取数据库中所有键的列表。

        返回:
            list: 包含所有键的列表。
        """
        return list(self.db.keys())

    def __setitem__(self, key, value):
        """
        重载[]操作符用于赋值，允许使用`db[key] = value`语法。
        """
        return self.set(key, value)

    def __getitem__(self, key):
        """
        重载[]操作符用于取值，允许使用`value = db[key]`语法。
        """
        value = self.get(key)
        if value is None:
            raise KeyError(key)
        return value

    def __enter__(self):
        """
        进入上下文管理器。
        不做任何操作，仅返回self用于修改。
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        退出上下文管理器。
        如果没有发生异常，自动保存更改。
        """
        if exc_type is None:  # 如果没有异常
            self.save()
        return False  # 不抑制异常