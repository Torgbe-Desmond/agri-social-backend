from fastapi import  HTTPException, Form, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from blog.database import get_async_db
from ...import schemas
import bcrypt
from .route import authRoute

@authRoute.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_async_db)
):
    try:
        # Check if username exists
        username_check = await db.execute(
            text("SELECT EXISTS(SELECT 1 FROM users WHERE username = :username)"),
            {"username": username}
        )
        if username_check.scalar():
            raise HTTPException(status_code=400, detail="Username already exists")

        # Check if email exists
        email_check = await db.execute(
            text("SELECT EXISTS(SELECT 1 FROM users WHERE email = :email)"),
            {"email": email}
        )
        if email_check.scalar():
            raise HTTPException(status_code=400, detail="Email already exists")

        # Hash the password
        hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        # Create new user
        result = await db.execute(
            text("""
                INSERT INTO users (username, email, password_hash, created_at)
                VALUES (:username, :email, :password_hash, NOW())
                RETURNING id, username, email
            """),
            {"username": username, "email": email, "password_hash": hashed_password}
        )
        await db.commit()

        new_user = result.fetchone()
        return {"id": new_user.id, "username": new_user.username, "email": new_user.email}

    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")
