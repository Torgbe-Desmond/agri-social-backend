# utils/jwt_handler.py
from datetime import datetime, timedelta
from jose import JWTError, jwt
ALGORITHM = "HS256"
import os
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 1 hour
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from dotenv import load_dotenv
load_dotenv()

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Public paths that should allow unauthenticated access
        public_paths = [
            "/auth/login",
            "/auth/register",
            "/auth/send-verification-email"
        ]
        
        # Skip auth for exact matches
        if request.url.path in public_paths:
            return await call_next(request)
        
        # Skip auth for paths starting with this prefix
        if request.url.path.startswith("/auth/generate-verification-token"):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing or invalid Authorization header"},
            )

        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(token,os.getenv("SECRET_KEY"), algorithms=[ALGORITHM])
            request.state.user = payload
        except JWTError:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid or expired token"},
            )

        return await call_next(request)


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})

    # Create token
    encoded_jwt = jwt.encode(to_encode, os.getenv("SECRET_KEY"), algorithm=ALGORITHM)
    return encoded_jwt


def verify_access_token(token: str):
    try:
        payload = jwt.decode(token, os.getenv("SECRET_KEY"), algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

