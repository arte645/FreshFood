from fastapi import FastAPI, HTTPException, Response, Request
import asyncio
from dotenv import load_dotenv
import os
from models.UserLoginSchema import UserLoginSchema
import grpc
from auth_pb2 import LoginRequest
from auth_pb2_grpc import AuthServiceStub

load_dotenv()

app = FastAPI()
auth_semaphore = asyncio.Semaphore(100)
data_semaphore = asyncio.Semaphore(200)

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
