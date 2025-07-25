from fastapi import  HTTPException, Form, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from blog.database import get_async_db
from .route import userRoute


@userRoute.get("/following/{user_id}/one/{current_user_id}")
async def is_following(user_id: str, current_user_id: str, db: AsyncSession = Depends(get_async_db)):
    try:
        query = text("""
            SELECT 1 FROM followers
            WHERE following_id = :user_id AND follower_id = :current_user_id
        """)
        result = await db.execute(query, {
            "current_user_id": current_user_id,
            "user_id": user_id
        })
        return {"isFollowing": bool(result.fetchone())}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))