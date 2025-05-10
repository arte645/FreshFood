from fastapi import FastAPI, Depends, HTTPException, Response, Request
import asyncio
from dotenv import load_dotenv
import os
from models.UserLoginSchema import UserLoginSchema
import grpc
from auth_pb2 import LoginRequest, Empty, callbackRequest
from auth_pb2_grpc import AuthServiceStub
from database_pb2_grpc import DatabaseServiceStub
from authx import AuthXConfig, AuthX
from supabase import create_client
from fastapi.responses import HTMLResponse
import json
from database_pb2 import GetRequest, GetResponse, PostRequest, PostResponse, UpdateRequest, UpdateResponse, DeleteRequest, DeleteResponse


load_dotenv()

app = FastAPI()
auth_semaphore = asyncio.Semaphore(100)
data_semaphore = asyncio.Semaphore(200)

config = AuthXConfig()
config.JWT_SECRET_KEY = os.getenv("JWT_KEY")
config.JWT_TOKEN_LOCATION = ["cookies"]
config.JWT_ACCESS_COOKIE_NAME = "access_token"

security = AuthX(config=config)

channel = grpc.insecure_channel(f"localhost:{os.getenv('authorizationHost')}")
auth_client = AuthServiceStub(channel)

channel = grpc.insecure_channel(f"localhost:{os.getenv('databaseHost')}")
database_client = DatabaseServiceStub(channel)

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

@app.get("/login/vk")
async def login():
        try:
            grpc_request = Empty()
            answer = auth_client.Login_vk(grpc_request)

            if answer.status_code != 200:
                raise HTTPException(status_code=answer.status_code, detail=answer.error_detail)
            
            return HTMLResponse(f"<html><head><meta http-equiv='refresh' content='0;url={answer.url}' /></head><body>Redirecting...</body></html>")

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка при запросе к сервису авторизации: {e}")


@app.get("/callback")
async def callback(code: str, state: str, response: Response, device_id: str = ""):
        try:
            grpc_request = callbackRequest(
                code=code,
                state=state,
                device_id = device_id
            )
            answer = auth_client.callback(grpc_request)

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

async def get_token_from_cookie(request: Request) -> str:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Access token not found in cookies")
    return request

@app.get("/user_settings", summary="Защищённая ручка", tags=["Основные ручки"])
async def user_settings(token_data=Depends(security.access_token_required)):
        try:
            grpc_request = GetRequest(
                table = "users",
                selected_columns = "(*)",
                rule_of_selection = f"user_id/{token_data.sub}"
            )
            answer = database_client.Get(grpc_request)

            if answer.status_code != 200:
                raise HTTPException(status_code=answer.status_code, detail=answer.error_detail)

            return json.loads(answer.data_json)
    
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка при запросе к сервису авторизации: {e}")
