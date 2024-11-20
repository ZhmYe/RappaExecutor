# import grpc
# from concurrent import futures
# from queue import Queue
#
# class GrpcEngine:
#     def __init__(self, task_pool: Queue) -> None:
#         """
#         task_pool: A shared task pool (thread-safe Queue) for storing tasks.
#         """
#         self.server = None
#         self.client = None
#         self.task_pool = task_pool
#
#     def send_request(self, target, message) -> None:
#         """
#         Client logic to send a request to another node.
#         """
#         # Example: gRPC client logic to send `message` to `target`
#         pass
#
#     def handle_request(self, request) -> None:
#         """
#         Server logic to handle incoming requests.
#         The request is parsed and added to the task pool.
#         """
#         print(f"Received request: {request}")
#         # Parse the request (you may define a protobuf schema for requests)
#         task_data = {"sign": request.sign, "model": request.model, "params": request.params}
#         self.task_pool.put(task_data)  # Add parsed task to the task pool
#         print(f"Task added to the pool: {task_data}")
#
#     def start_server(self, port=50051):
#         """
#         Start the gRPC server to listen for incoming requests.
#         """
#         self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
#         # Add your gRPC service definition here (not shown in this template)
#         print(f"gRPC server started on port {port}")
#         self.server.add_insecure_port(f"[::]:{port}")
#         self.server.start()
#         self.server.wait_for_termination()
