from fastapi import FastAPI, Depends, HTTPException, Response, Request
import asyncio
from dotenv import load_dotenv
import os
from models.UserLoginSchema import UserLoginSchema
import grpc
from auth_pb2 import LoginRequest
from auth_pb2_grpc import AuthServiceStub
from authx import AuthXConfig, AuthX
from supabase import create_client, Client

load_dotenv()

app = FastAPI()
auth_semaphore = asyncio.Semaphore(100)
data_semaphore = asyncio.Semaphore(200)

config = AuthXConfig()
config.JWT_SECRET_KEY = os.getenv("JWT_KEY")
config.JWT_TOKEN_LOCATION = ["cookies"]
config.JWT_ACCESS_COOKIE_NAME = "access_token"

security = AuthX(config=config)

channel = grpc.insecure_channel(os.getenv("authorizationHost"))
auth_client = AuthServiceStub(channel)

@app.post("/login", summary="Зайти в аккаунт", tags=["Основные ручки"])
async def login(user: UserLoginSchema, response: Response):
    async with auth_semaphore:
        try:
            grpc_request = LoginRequest(
                user_name=user.userName,
                user_password=user.userPassword
            )
            answer = auth_client.Login(grpc_request)
            
            if answer.status_code != 200:
                raise HTTPException(status_code=answer.status_code, detail=answer.error_detail)
            
            response.set_cookie(
                key="access_token",
                value=answer.access_token,
                max_age=3600
            )
            return {"access_token": answer.access_token}
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка при запросе к сервису авторизации: {e}")


@app.get("/user_settings", summary="Защищённая ручка", tags=["Основные ручки"])
async def user_settings(token_data=Depends(security.access_token_required)):
    supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
    response = (
            supabase.table("users")
            .select("*")
            .eq("user_id", token_data.sub)
            .execute()
        )
    return response.data
