
from fastapi import  HTTPException, Form, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from blog.database import get_async_db
from .route import userRoute

@userRoute.post("/follow/{user_id}/one/{localUser}")
async def toggle_follow(user_id: str, localUser: str, db: AsyncSession = Depends(get_async_db)):
    try:
        result = await db.execute(text("""
            SELECT 1 FROM followers 
            WHERE following_id = :user_id AND follower_id = :localUser
        """), {"localUser": localUser, "user_id": user_id})

        if result.fetchone():
            await db.execute(text("""
                DELETE FROM followers 
                WHERE following_id = :user_id AND follower_id = :localUser
            """), {"localUser": localUser, "user_id": user_id})
            is_following = False
        else:
            await db.execute(text("""
                INSERT INTO followers (following_id, follower_id) 
                VALUES (:user_id, :localUser)
            """), {"localUser": localUser, "user_id": user_id})
            is_following = True

        await db.commit()
        return {"follow": is_following}

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))