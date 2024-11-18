import unittest
from queue import Queue
from unittest.mock import patch
from node.Task.task import Task
from node.format import TaskPoolItem
from logger.logger import logWriter as log
from network.Grpc.FakeGrpc import FakeGrpcEngine  # Replace 'your_module' with the actual module name


class TestFakeGrpcEngine(unittest.TestCase):
    def setUp(self):
        """
        初始化测试环境
        """
        self.task_pool = Queue()  # 创建一个任务队列
        self.fake_engine = FakeGrpcEngine(self.task_pool)  # 初始化 FakeGrpcEngine

    def test_generate_fake_request(self):
        """
        测试任务生成逻辑
        """
        tid = 1
        sign = "0x1"
        slot = 2

        task = self.fake_engine.generate_fake_request(tid, sign, slot)

        self.assertIsInstance(task, TaskPoolItem)
        self.assertEqual(task.id, tid)
        self.assertEqual(task.sign, sign)
        self.assertEqual(task.slot.id, slot)
        self.assertEqual(task.model(), "ctgan")

    def test_handle_request(self):
        """
        测试任务处理逻辑
        """
        initial_task_count = self.task_pool.qsize()
        self.fake_engine.handle_request()

        # 检查任务是否添加到队列中
        self.assertEqual(self.task_pool.qsize(), initial_task_count + 1)

        # 检查任务的内容是否符合生成逻辑
        task = self.task_pool.get()
        self.assertIsInstance(task, TaskPoolItem)
        self.assertEqual(task.sign, "0x{}".format(self.fake_engine.sign))
        self.assertEqual(task.slot.id, self.fake_engine.slot)

    @patch("time.sleep", return_value=None)  # Mock time.sleep for faster testing
    def test_start_server(self, _):
        """
        测试模拟 GRPC 服务器的运行逻辑
        """
        self.fake_engine.max_task_nb_slot = 3
        self.fake_engine.start_server(port=12345)

        # 检查任务队列是否填充了正确数量的任务
        self.assertEqual(self.task_pool.qsize(), 20)

        # 检查任务的内容
        while not self.task_pool.empty():
            task = self.task_pool.get()
            self.assertIsInstance(task, TaskPoolItem)
            self.assertIn("0x", task.sign)
            self.assertLessEqual(task.slot.id, self.fake_engine.max_task_nb_slot)
