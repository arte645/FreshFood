import subprocess
import time
import grpc
from auth_pb2_grpc import AuthServiceStub
from auth_pb2 import LoginRequest

def wait_for_grpc_server(port: int, timeout: int = 10):
    """Ожидание готовности gRPC сервера"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            channel = grpc.insecure_channel(f"localhost:{port}")
            stub = AuthServiceStub(channel)
            # Пробуем сделать тестовый вызов
            stub.Login(LoginRequest(user_name="test", user_password="test"))
            return True
        except grpc.RpcError:
            time.sleep(0.5)
    return False

def run():
    # Запуск gRPC сервера (authorizationAPI)
    grpc_process = subprocess.Popen(["python", "authorizationAPI.py"])
    
    # Ждем пока gRPC сервер станет доступен
    if not wait_for_grpc_server(50051):
        print("Не удалось подключиться к gRPC серверу")
        grpc_process.terminate()
        return
    
    # Запуск FastAPI gateway
    gateway_process = subprocess.Popen(["uvicorn", "gatewayApi:app", "--port", "8000"])
    
    try:
        # Ожидаем завершения процессов (которого никогда не произойдет)
        gateway_process.wait()
        grpc_process.wait()
    except KeyboardInterrupt:
        # Обработка Ctrl+C для graceful shutdown
        print("\nЗавершение работы сервисов...")
        gateway_process.terminate()
        grpc_process.terminate()
        gateway_process.wait()
        grpc_process.wait()

if __name__ == "__main__":
    run()