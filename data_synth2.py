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
    def __init__(
        self,
        model_name,
        max_total_size_gb=1024 * 15,
        max_chunk_size_gb=10,
        chunk_counter=0,
        output_dir="/hdd3/baed"
    ):
        self.model_path = get_model_root()
        self.loader = ModelLoader(self.model_path)
        self.instance = self.loader.load(model_name, True)
        self.max_total_size_bytes = max_total_size_gb * 1024 ** 3  # Total data size limit
        self.max_chunk_size_bytes = max_chunk_size_gb * 1024 ** 3  # Per-chunk size limit
        self.output_dir = Path(output_dir)
        self.chunk_counter = chunk_counter
        self.total_size = 0
        self.current_chunk_path = None
        self.current_chunk_size = 0
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.loop = asyncio.get_event_loop()

        # Set up logging
        self._setup_logging()

        # Ensure output directory exists
        self.output_dir.mkdir(exist_ok=True, parents=True)

    def _setup_logging(self):
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
        try:
            self.logger.info(f"Generating output for {num_records} records...")

            # Generate output
            output = await self.loop.run_in_executor(
                self.executor,
                lambda: self.instance.generate_output(num_records)
            )

            json_data = chunk2json(output.format_json()['output'])
            json_size = len(json_data.encode('utf-8'))

            # Check if total size limit is reached
            if self.total_size + json_size > self.max_total_size_bytes:
                self.logger.warning(
                    f"Reached maximum total size limit of {self.max_total_size_bytes / (1024 ** 3):.2f}GB"
                )
                return False

            # Determine if we need to start a new chunk file
            if (
                self.current_chunk_path is None or
                self.current_chunk_size + json_size > self.max_chunk_size_bytes
            ):
                if self.current_chunk_path is not None:
                    self.logger.info(
                        f"Chunk {self.chunk_counter} reached size limit. "
                        f"Current size: {self.current_chunk_size / (1024 ** 3):.2f}GB"
                    )

                # Start a new chunk file
                self.chunk_counter += 1
                self.current_chunk_path = self.output_dir / f"chunk_{self.chunk_counter:04d}.json"
                self.current_chunk_size = 0  # Reset chunk size

            # Determine write mode
            mode = 'w' if self.current_chunk_size == 0 else 'a'

            # Write to file
            await self.loop.run_in_executor(
                self.executor,
                self._write_to_file,
                self.current_chunk_path,
                json_data,
                mode
            )

            # Update sizes
            self.current_chunk_size += json_size
            self.total_size += json_size

            self.logger.info(
                f"Wrote {json_size / (1024 ** 2):.2f}MB to chunk {self.chunk_counter}. "
                f"Current size: {self.current_chunk_size / (1024 ** 3):.2f}GB"
            )
            return True

        except Exception as e:
            self.logger.error(f"Error generating/writing chunk: {str(e)}", exc_info=True)
            return False

    def _write_to_file(self, filename, data, mode='w'):
        with open(filename, mode, encoding='utf-8') as f:
            f.write(data)
        self.logger.info(f"Saved chunk to {filename} (Size: {len(data.encode('utf-8')) / (1024 ** 2):.2f}MB)")

    async def finalize(self):
        self.executor.shutdown(wait=True)
        self.logger.info(
            f"Generation complete. Total chunks: {self.chunk_counter}, "
            f"Total size: {self.total_size / (1024 ** 3):.2f}GB"
        )


# Convert chunk to JSON
def chunk2json(chunk):
    if isinstance(chunk, DataFrame):
        return chunk.to_json(orient="records")
    elif isinstance(chunk, list) and isinstance(chunk[0], nx.Graph):
        return json.dumps([nx.node_link_data(g) for g in chunk])
    else:
        return json.dumps(chunk)


# Example async main function
async def main():
    generator = AsyncChunkedOutputGenerator("BAED", max_chunk_size_gb=10)

    try:
        # Generate fixed-size chunks until max total size is reached
        while True:
            success = await generator.generate_chunked_output(10000)  # Fixed number of records per chunk
            if not success:
                break
    except Exception as e:
        generator.logger.error("Error in main loop", exc_info=True)
    finally:
        await generator.finalize()


if __name__ == "__main__":
    asyncio.run(main())