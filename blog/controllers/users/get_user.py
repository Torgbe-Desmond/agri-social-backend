
from fastapi import  HTTPException, Form, Depends, status,Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from blog.database import get_async_db
from .route import userRoute
from . import _schema

@userRoute.get('/', response_model=_schema.User)
async def get_user(request:Request, db: AsyncSession = Depends(get_async_db)):
    current_user = request.state.user 
    result = await db.execute(text("""
    SELECT 
        u.id,
        u.username,
        u.email,
        u.created_at,
        u.city,
        u.firstname,
        u.lastname,
        u.reference_id,
        (SELECT COUNT (*) FROM notifications WHERE user_id = u.id AND is_read = 0) as notification_count,
        COALESCE(u.user_image, '') AS user_image,
        (
            SELECT COUNT(*) FROM followers WHERE follower_id = u.id
        ) AS following,
        (
            SELECT COUNT(*) FROM followers WHERE following_id = u.id
        ) AS followers
    FROM users u
    WHERE u.id = :userId
    """), {"userId": current_user.get("user_id")})
    user = result.mappings().fetchone()

    if not user:
        raise HTTPException(status_code=404, detail="No users found")

    return user 
