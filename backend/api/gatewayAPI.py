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
import httpx
import base64, hashlib, secrets
import base64, hashlib, secrets, os
from fastapi import FastAPI, Request
from dotenv import load_dotenv
import httpx
from urllib.parse import urlencode
from fastapi import FastAPI, Depends, HTTPException, Response, Request
from fastapi import FastAPI, Request, HTTPException
import secrets
import hashlib
import base64
import httpx
from fastapi.responses import HTMLResponse

import httpx


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
        
session_store = {}

def generate_code_verifier():
    return base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b'=').decode()

def generate_code_challenge(verifier):
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b'=').decode()

@app.get("/login/vk")
async def login():
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)
    state = secrets.token_urlsafe(16)

    session_store[state] = {
    "code_verifier": code_verifier,
    }

    params = {
        "client_id": os.getenv("VK_ID"),
        "redirect_uri": os.getenv("VK_REDIRECT_URI"),
        "response_type": "code",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
        "scope": "vkid.personal_info",
    }

    url = "https://id.vk.com/authorize?" + "&".join([f"{k}={v}" for k, v in params.items()])
    return HTMLResponse(f"<html><head><meta http-equiv='refresh' content='0;url={url}' /></head><body>Redirecting...</body></html>")

@app.get("/callback")
async def callback(code: str, state: str, response: Response, device_id: str = ""):
    if state not in session_store:
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    code_verifier = session_store[state]["code_verifier"]

    data = {
        "grant_type": "authorization_code",
        "client_id": os.getenv("VK_ID"),
        "client_secret": os.getenv("VK_CLIENT_SECRET"),
        "code": code,
        "code_verifier": code_verifier,
        "redirect_uri": os.getenv("VK_REDIRECT_URI")+"/check",
        "device_id": device_id,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post("https://id.vk.com/oauth2/auth", data=data)

    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail=f"VK error: {resp.text}")

    tokens = resp.json()
    response.set_cookie(
                key="access_token",
                value=tokens["access_token"],
                max_age=3600
            )
    return {"access_token": tokens["access_token"]}

async def get_token_from_cookie(request: Request) -> str:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Access token not found in cookies")
    return request

@app.get("/create/user")
async def get_user_info(response: Response, request=Depends(get_token_from_cookie)):
    async with httpx.AsyncClient() as client:
        data = {
        "client_id": os.getenv("VK_ID"),
        "access_token":request.cookies.get("access_token")
    }
        resp = await client.post(
        "https://id.vk.com/oauth2/user_info",
        data = data
        )
        if resp.status_code != 200:
            raise Exception(f"VK ID error: {resp.status_code}, {resp.text}")
        answer = resp.json()["user"]
        supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
        resp = (
            supabase.table("users")
            .insert({"user_id": answer["user_id"],
                    "login": answer["first_name"]+answer["last_name"],
                    "password_hash":"qwerty123",
                    "first_name":answer["first_name"],
                    "last_name":answer["last_name"],
                    "email":None,"address": None,"diet_type": None, "phone_number":None})
            .execute()
        )

        response.set_cookie(
                key="access_token",
                value=security.create_access_token(uid=str(answer["user_id"])),
                max_age=3600
            )

        return {"status":"success"}


@app.get("/user_settings", summary="Защищённая ручка", tags=["Основные ручки"])
async def user_settings(token_data=Depends(security.access_token_required)):
    supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
    resp = (
            supabase.table("users")
            .select("*")
            .eq("user_id", token_data.sub)
            .execute()
        )
    return resp.data
