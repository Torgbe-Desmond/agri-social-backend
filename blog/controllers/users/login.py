from fastapi import  HTTPException, Form, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from blog.database import get_async_db
from .route import userRoute
import bcrypt
from ...middleware.authMiddleware import create_access_token,verify_access_token

@userRoute.post("/login")
async def login(
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_async_db)
):
    try:
        result = await db.execute(text("SELECT * FROM users WHERE email = :email"), {"email": email})
        user = result.fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="Wrong email or password")

        if not bcrypt.checkpw(password.encode("utf-8"), user.password_hash.encode("utf-8")):
            raise HTTPException(status_code=401, detail="Wrong email or password")

        # ✅ Generate token with user ID and username
        token = create_access_token(data={"user_id": user.id, "username": user.username})

        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "user_image": user.user_image,
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))