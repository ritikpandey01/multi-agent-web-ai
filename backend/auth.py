"""Authentication module — JWT tokens + password hashing.

Endpoints:
  POST /auth/register — Create a new account
  POST /auth/login    — Login and get JWT token
  GET  /auth/me       — Get current user info

Uses Supabase for user storage, bcrypt for password hashing, PyJWT for tokens.
"""

import os
import jwt
import bcrypt
import uuid
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel, Field, EmailStr
from fastapi import APIRouter, HTTPException, Depends, Request
from dotenv import load_dotenv

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET", "webintel-secret-key-change-in-production-2026")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 72

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ─── Models ─────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=6)

class LoginRequest(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    created_at: str


# ─── Password Utils ─────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


# ─── JWT Utils ───────────────────────────────────────────────────────────────

def create_token(user_id: str, username: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "email": email,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ─── Auth Dependency ─────────────────────────────────────────────────────────

async def get_current_user(request: Request) -> dict:
    """Extract and validate JWT from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    
    token = auth_header.split(" ", 1)[1]
    payload = decode_token(token)
    return {
        "id": payload["sub"],
        "username": payload["username"],
        "email": payload["email"],
    }


# ─── Supabase User Operations ───────────────────────────────────────────────

def _get_users_client():
    from services.supabase_service import _get_client
    return _get_client()


# ─── Routes ──────────────────────────────────────────────────────────────────

@router.post("/register")
async def register(req: RegisterRequest):
    """Create a new user account."""
    client = _get_users_client()
    
    # Check if email already exists
    existing = client.table("users").select("id").eq("email", req.email).execute()
    if existing.data:
        raise HTTPException(status_code=409, detail="Email already registered")
    
    # Check if username exists
    existing_user = client.table("users").select("id").eq("username", req.username).execute()
    if existing_user.data:
        raise HTTPException(status_code=409, detail="Username already taken")
    
    # Create user
    user_id = str(uuid.uuid4())
    user_data = {
        "id": user_id,
        "username": req.username,
        "email": req.email,
        "password_hash": hash_password(req.password),
        "created_at": datetime.utcnow().isoformat(),
    }
    
    try:
        client.table("users").insert(user_data).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create user: {str(e)}")
    
    token = create_token(user_id, req.username, req.email)
    
    return {
        "token": token,
        "user": {
            "id": user_id,
            "username": req.username,
            "email": req.email,
        },
        "message": "Account created successfully",
    }


@router.post("/login")
async def login(req: LoginRequest):
    """Login with email and password."""
    client = _get_users_client()
    
    result = client.table("users").select("*").eq("email", req.email).execute()
    if not result.data:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    user = result.data[0]
    
    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    token = create_token(user["id"], user["username"], user["email"])
    
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
        },
        "message": "Login successful",
    }


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    """Get current authenticated user info."""
    return {"user": user}
