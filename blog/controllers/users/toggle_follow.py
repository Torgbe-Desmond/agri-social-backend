
from fastapi import  HTTPException, Form, Depends, status,Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from blog.database import get_async_db
from .route import userRoute

@userRoute.post("/follow") 
async def toggle_follow(request:Request,user_id: str = Form(...), db: AsyncSession = Depends(get_async_db)):
    try:
        current_user = request.state.user
        result = await db.execute(text("""
            SELECT 1 FROM followers 
            WHERE following_id = :user_id AND follower_id = :localUser
        """), {"localUser": current_user.get("user_id"), "user_id": user_id})

        if result.fetchone():
            await db.execute(text("""
                DELETE FROM followers 
                WHERE following_id = :user_id AND follower_id = :localUser
            """), {"localUser": current_user.get("user_id"), "user_id": user_id})
            is_following = False
        else:
            await db.execute(text("""
                INSERT INTO followers (following_id, follower_id) 
                VALUES (:user_id, :localUser)
            """), {"localUser": current_user.get("user_id"), "user_id": user_id})
            is_following = True

        await db.commit()
        return {"follow": is_following}

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))