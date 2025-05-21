from concurrent import futures
import grpc
from auth_pb2 import LoginResponse, Empty, callbackResponse, callbackRequest, Login_vkResponse, RegistrationResponse, RegistrationRequest
from auth_pb2_grpc import AuthServiceServicer, add_AuthServiceServicer_to_server
from fastapi import FastAPI, Depends, HTTPException, Response, Request
import asyncio
from dotenv import load_dotenv
import os
from auth_pb2 import LoginRequest
from auth_pb2_grpc import AuthServiceStub
from authx import AuthXConfig, AuthX
from supabase import create_client, Client
import httpx
import base64, hashlib, secrets
from fastapi.responses import HTMLResponse
from database_pb2 import GetRequest, GetResponse, PostRequest, PostResponse, UpdateRequest, UpdateResponse, DeleteRequest, DeleteResponse
from database_pb2_grpc import DatabaseServiceStub
import json
import time
import bcrypt
import random

load_dotenv()

config = AuthXConfig()
config.JWT_SECRET_KEY = os.getenv("JWT_KEY")
config.JWT_ACCESS_COOKIE_NAME = "access_token"

security = AuthX(config=config)
channel = grpc.insecure_channel(f"localhost:{os.getenv('databaseHost')}")
database_client = DatabaseServiceStub(channel)

class AuthService(AuthServiceServicer):
    def __init__(self):
        pass

    def generate_user_id(self) -> int:
        timestamp = int(time.time() * 1000)  # миллисекунды
        random_part = random.randint(0, 99999)  # 5-значное случайное число
        unique_id = int(f"{timestamp}{random_part:05d}"[:18])  # обрезаем до 18 цифр
        return unique_id
    
    def Login(self, request, context):
        try:
            grpc_request = GetRequest(
                table = "users",
                selected_columns = "user_id, login, password_hash",
                rule_of_selection = f"login/{request.user_name}"
            )
            answer = database_client.Get(grpc_request)
            data_json = json.loads(answer.data_json)
            print(f"{self.hash_password(request.user_password)}----------{data_json[0]['password_hash']}")
            if len(data_json) <= 0:
                return LoginResponse(
                    status_code=401,
                    error_detail="login is non-existent"
                )
            elif self.hash_password(request.user_password) != data_json[0]['password_hash']:
                return LoginResponse(
                    status_code=400,
                    error_detail="wrong password"
                )
            
            token = security.create_access_token(uid=str(data_json[0]['user_id']))
            return LoginResponse(
                access_token=token,
                status_code=200
            )
        except Exception as e:
            raise e

    def hash_password(self, password: str) -> str:
        salt = os.getenv("JWT_KEY")
        return hashlib.sha256((salt + password).encode('utf-8')).hexdigest()

    def Registration(self, request, context=None, first_name=None, last_name=None, user_id = None):
        if not user_id:
            user_id = self.generate_user_id()
        inserted_columns_and_data = {"user_id": user_id,
                        "login": request.login,
                        "password_hash": self.hash_password(request.password),
                        "first_name":first_name,
                        "last_name":last_name,
                        "email":None,"address": None,"diet_type": None, "phone_number":None}
        inserted_columns_string = json.dumps(inserted_columns_and_data)
        grpc_request = PostRequest(
                    table = "users",
                    inserted_columns_and_data = inserted_columns_string
                )
        ans = database_client.Post(grpc_request)
        return RegistrationResponse(status_code = 200, access_token = str(security.create_access_token(uid=str(user_id))))
    
    session_store = {}

    def generate_code_verifier(self):
        return base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b'=').decode()

    def generate_code_challenge(self, verifier):
        digest = hashlib.sha256(verifier.encode()).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b'=').decode()

    def Login_vk(self, request, context):
        code_verifier = self.generate_code_verifier()
        code_challenge = self.generate_code_challenge(code_verifier)
        state = secrets.token_urlsafe(16)

        self.session_store[state] = {
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
        url=f"<html><head><meta http-equiv='refresh' content='0;url={url}' /></head><body>Redirecting...</body></html>"
        return Login_vkResponse(
            url=url,
            status_code=200
        )

    def callback(self, request, context):
        if request.state not in self.session_store:
            raise HTTPException(status_code=400, detail="Invalid or expired state")

        code_verifier = self.session_store[request.state]["code_verifier"]

        data = {
            "grant_type": "authorization_code",
            "client_id": os.getenv("VK_ID"),
            "client_secret": os.getenv("VK_CLIENT_SECRET"),
            "code": request.code,
            "code_verifier": code_verifier,
            "redirect_uri": os.getenv("VK_REDIRECT_URI")+"/check",
            "device_id": request.device_id,
        }
        with httpx.Client() as client:
            resp = client.post("https://id.vk.com/oauth2/auth", data=data)

        if resp.status_code != 200:
            raise HTTPException(status_code=500, detail=f"VK error: {resp.text}")

        tokens = resp.json()
        return callbackResponse(
            access_token=self.get_user_info(tokens["access_token"]),
            status_code=200
        )
    

    def get_user_info(self, access_token):
        with httpx.Client() as client:
            data = {
            "client_id": os.getenv("VK_ID"),
            "access_token": access_token
            }
            resp = client.post(
            "https://id.vk.com/oauth2/user_info",
            data = data
            )
            if resp.status_code != 200:
                raise Exception(f"VK ID error: {resp.status_code}, {resp.text}")
            answer = resp.json()["user"]
            try:
                ans = self.Registration(request=RegistrationRequest(login = "vk_"+answer["first_name"]+answer["last_name"],
                                                            password = self.hash_password("qwerty123")),
                                                            first_name=answer["first_name"],
                                                            last_name=answer["last_name"],
                                                            user_id=answer["user_id"])
                return ans.access_token
            except Exception as e:
                raise e

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    add_AuthServiceServicer_to_server(AuthService(), server)
    server.add_insecure_port(f"[::]:{os.getenv('authorizationHost')}")
    server.start()
    server.wait_for_termination()


serve()
