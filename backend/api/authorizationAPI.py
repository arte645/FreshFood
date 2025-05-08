from concurrent import futures
import grpc
from auth_pb2 import LoginResponse
from auth_pb2_grpc import AuthServiceServicer, add_AuthServiceServicer_to_server
from authx import AuthXConfig, AuthX
from dotenv import load_dotenv
from supabase import create_client, Client
import os

load_dotenv()

config = AuthXConfig()
config.JWT_SECRET_KEY = os.getenv("JWT_KEY")
config.JWT_ACCESS_COOKIE_NAME = "access_token"

security = AuthX(config=config)

class AuthService(AuthServiceServicer):
    def __init__(self):
        self.supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
    
    def Login(self, request, context):
        response = (
            self.supabase.table("users")
            .select("login, password_hash")
            .eq("login", request.user_name)
            .execute()
        )
        
        if len(response.data) <= 0:
            return LoginResponse(
                status_code=401,
                error_detail="login is non-existent"
            )
        elif request.user_password != response.data[0]['password_hash']:
            return LoginResponse(
                status_code=400,
                error_detail="wrong password"
            )
        
        token = security.create_access_token(uid="smthg")
        return LoginResponse(
            access_token=token,
            status_code=200
        )

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    add_AuthServiceServicer_to_server(AuthService(), server)
    server.add_insecure_port("[::]:50051")
    server.start()
    server.wait_for_termination()
