import json
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import datetime

import networkx as nx
from pandas import DataFrame

from model.loader import ModelLoader
from utils.function.func import get_model_root


class AsyncChunkedOutputGenerator:
    def __init__(self, model_name, max_total_size_gb=1024 * 15, chunck_counter=0, output_dir="/hdd4/finka"):
        self.model_path = get_model_root()
        self.loader = ModelLoader(self.model_path)
        self.instance = self.loader.load(model_name, True)
        self.max_total_size_bytes = max_total_size_gb * 1024 ** 3  # 1TB = 1024GB
        self.output_dir = Path(output_dir)
        self.chunk_counter = chunck_counter
        self.total_size = 0
        self.executor = ThreadPoolExecutor(max_workers=4)  # 异步写入线程池
        self.loop = asyncio.get_event_loop()

        # Set up logging
        self._setup_logging()

        # 确保输出目录存在
        self.output_dir.mkdir(exist_ok=True, parents=True)

    def _setup_logging(self):
        """Configure logging to both console and file"""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"generator_{timestamp}.log"

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Initialized AsyncChunkedOutputGenerator. Logging to {log_file}")

    async def generate_chunked_output(self, num_records):
        """生成并立即写入输出，参数num_records表示每次处理多少条数据"""
        try:
            self.logger.info(f"Generating output for {num_records} records...")

            # 异步生成输出
            output = await self.loop.run_in_executor(
                self.executor,
                lambda: self.instance.generate_output(num_records)
            )

            json_data = chunk2json(output.format_json()['output'])
            json_size = len(json_data.encode('utf-8'))

            # 检查是否超过总大小限制
            if self.total_size + json_size > self.max_total_size_bytes:
                self.logger.warning(f"Reached maximum total size limit of {self.max_total_size_bytes / (1024 ** 3)}GB")
                return False

            # 异步写入文件
            chunk_filename = self.output_dir / f"chunk_{self.chunk_counter:04d}.json"
            await self.loop.run_in_executor(
                self.executor,
                self._write_to_file,
                chunk_filename,
                json_data
            )

            self.chunk_counter += 1
            self.total_size += json_size

            self.logger.info(
                f"Successfully generated chunk {self.chunk_counter} with size {json_size / (1024 ** 2):.2f}MB")
            return True

        except Exception as e:
            self.logger.error(f"Error generating/writing chunk: {str(e)}", exc_info=True)
            return False

    def _write_to_file(self, filename, data):
        """同步写入文件的方法"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(data)
        self.logger.info(f"Saved chunk to {filename} (Size: {len(data.encode('utf-8')) / (1024 ** 2):.2f}MB)")

    async def finalize(self):
        """关闭资源"""
        self.executor.shutdown(wait=True)
        self.logger.info(
            f"Generation complete. Total chunks: {self.chunk_counter}, Total size: {self.total_size / (1024 ** 3):.2f}GB")


# 将结果转换为json
def chunk2json(chunk):
    if isinstance(chunk, DataFrame):
        return chunk.to_json()
    elif isinstance(chunk, list) and isinstance(chunk[0], nx.Graph):
        json_chunk = []
        for item in chunk:
            json_chunk.append(nx.node_link_data(item))
        return json.dumps(json_chunk)


# 异步使用示例
async def main():
    generator = AsyncChunkedOutputGenerator("FINKAN")

    try:
        # 示例：每次处理1000条数据，共处理100次
        for i in range(10000000000):
            success = await generator.generate_chunked_output(1700000 * 3)  # 每次处理1000条数据
            if not success:
                break

            generator.logger.info(
                f"Progress: {generator.total_size / (1024 ** 3):.2f}GB / {generator.max_total_size_bytes / (1024 ** 3):.2f}GB")

    except Exception as e:
        generator.logger.error("Error in main loop", exc_info=True)
    finally:
        await generator.finalize()


if __name__ == "__main__":
    asyncio.run(main())
