import base64, hashlib, secrets, os
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
import httpx
from urllib.parse import urlencode
from fastapi import FastAPI, Depends, HTTPException, Response, Request

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
import secrets
import hashlib
import base64
import httpx
from fastapi.responses import HTMLResponse

load_dotenv()
app = FastAPI()

session_store = {}

def generate_code_verifier():
    return base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b'=').decode()

def generate_code_challenge(verifier):
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b'=').decode()

@app.get("/login")
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

import httpx

@app.get("/callback/check")
async def get_user_info(access_token) -> dict:

        return access_token