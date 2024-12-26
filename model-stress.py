import asyncio
import httpx
import time
import json
import random
import traceback
import argparse
from tqdm import tqdm

class HttpBenchmark:
    def __init__(self, url, total_requests, concurrency, dataset_path):
        self.url = url
        self.total_requests = total_requests
        self.concurrency = concurrency
        self.dataset_path = dataset_path  # 数据集路径
        self.success_count = 0
        self.failure_count = 0
        self.total_time = 0
        self.completed_requests = 0  # 用于统计已完成的请求数
        self.data_pool = self.load_dataset()  # 预加载数据集
        self.progress_bar = tqdm(total=self.total_requests, desc="Benchmark Progress")  # 初始化进度条

    def load_dataset(self):
        """
        加载 txt 数据集，每一行是一个 prompt。
        """
        try:
            with open(self.dataset_path, "r", encoding="utf-8") as f:
                return [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"加载数据集失败: {e}")
            return []

    def get_random_prompt(self):
        """
        从数据池中随机抽取一个 prompt。
        """
        if not self.data_pool:
            raise ValueError("数据池为空，请检查数据集文件。")
        return random.choice(self.data_pool)

    async def make_request(self, client, semaphore,i):
        async with semaphore:  # 控制并发量
            try:
                start_time = time.monotonic()

                # 从数据池中随机抽取 prompt
                prompt = self.get_random_prompt()
                data = {
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.6,
                    "max_tokens": 9999
                }

                response = await client.post(self.url, json=data)
                end_time = time.monotonic()

                elapsed_time = end_time - start_time
                self.total_time += elapsed_time
                self.completed_requests += 1

                if response.status_code == 200:
                    self.success_count += 1
                    #print(f"#######{i}#########\nstatus: {response.status_code}\nelapsed_time: {elapsed_time:.2f} seconds\nresponse_text: {response.json()["text"][0]}")
                else:
                    self.failure_count += 1
                    #print(f"########{i}########\nstatus: {response.status_code}\nelapsed_time: {elapsed_time:.2f} seconds\nerror: {response.text}")

            except Exception as e:
                self.failure_count += 1
                traceback.print_exc()  # 打印详细的异常堆栈
            finally:
                self.progress_bar.update(1)

    async def run(self):
        semaphore = asyncio.Semaphore(self.concurrency)  # 限制并发数量
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            tasks = []
            for i in range(self.total_requests):
                # 每次提交一个新任务
                tasks.append(asyncio.create_task(self.make_request(client, semaphore,i)))
            await asyncio.gather(*tasks)  # 等待所有任务完成

    def run_benchmark(self):
        start_time = time.monotonic()
        asyncio.run(self.run())
        end_time = time.monotonic()

        total_duration = end_time - start_time
        if total_duration > 0:
            qps = self.completed_requests / total_duration
        else:
            qps = 0

        if self.success_count > 0:
            average_time = self.total_time / self.success_count
        else:
            average_time = 0

        # Beautify and print final stats
        print("\n" + "#" * 50)
        print(f"{'Metric':<25} {'Value'}")
        print("-" * 50)
        print(f"{'Total Requests:':<25} {self.total_requests}")
        print(f"{'Concurrency:':<25} {self.concurrency}")
        print(f"{'Success Count:':<25} {self.success_count}")
        print(f"{'Failure Count:':<25} {self.failure_count}")
        print(f"{'Total Duration:':<25} {total_duration:.2f} seconds")
        print(f"{'Average Response Time:':<25} {average_time:.2f} seconds")
        print(f"{'QPS:':<25} {qps:.2f}")
        print("#" * 50 + "\n")
        
        self.progress_bar.close()


if __name__ == "__main__":
    # Example usage:
    # url = "http://127.0.0.1:8000/generate"  # Replace with your target URL
    # total_requests = 9    # Total number of requests
    # concurrency = 3      # Number of concurrent workers
    # dataset_path = "test.txt"  # 数据集文件路径

    # 使用 argparse 解析命令行参数
    parser = argparse.ArgumentParser(description="HTTP Benchmark Tool")
    parser.add_argument("--url", type=str, required=True, help="The target URL for the benchmark")
    parser.add_argument("--total", type=int, required=True, help="The total number of requests to send")
    parser.add_argument("--concurrency", type=int, required=True, help="The number of concurrent workers")
    parser.add_argument("--dataset", type=str, required=True, help="Path to the dataset file")

    args = parser.parse_args()

    # 从命令行参数读取配置
    benchmark = HttpBenchmark(
        url=args.url,
        total_requests=args.total,
        concurrency=args.concurrency,
        dataset_path=args.dataset
    )
    benchmark.run_benchmark()
