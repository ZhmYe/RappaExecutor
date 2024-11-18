import unittest
from node.node import BHExecutionNode
from config.config import BHExecutionNodeGlobalConfig


class TestBHExecutionNode(unittest.TestCase):
    def setUp(self):
        """
        初始化测试环境
        """
        # 设置全局调试模式为 True
        BHExecutionNodeGlobalConfig.set_debug(True)
        self.node = BHExecutionNode()

    def test_task_processing(self):
        """
        测试节点是否能正确处理由 FakeGrpcEngine 生成的任务
        """
        # 启动节点任务处理逻辑
        import threading
        node_thread = threading.Thread(target=self.node.start)
        node_thread.daemon = True  # 确保测试结束时线程自动关闭
        node_thread.start()

        # 等待任务生成并处理
        import time
        time.sleep(30)  # 等待 FakeGrpcEngine 生成任务并让节点处理

        # 检查任务池是否被清空（任务被消费）
        self.assertTrue(self.node.task_pool.empty(), "Task pool should be empty after processing")

        # 检查任务是否被正确处理并记录
        self.assertGreater(len(self.node.task_map), 0, "Task map should contain processed tasks")
        for sign, index in self.node.task_map.items():
            task = self.node.tasks[index]
            self.assertIsNotNone(task, f"Task with sign {sign} should exist in tasks")
            self.assertEqual(task.sign, sign)



