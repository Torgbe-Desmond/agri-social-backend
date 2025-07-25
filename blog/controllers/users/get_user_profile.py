from fastapi import  HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from blog.database import get_async_db
from .route import userRoute
from ...import schemas
from sqlalchemy import text
from typing import List

@userRoute.get('/profile/', response_model=List[schemas.Search])
async def get_user_profile(username: str = Query(...), db: AsyncSession = Depends(get_async_db)):
    query_stmt = text("SELECT id, username, user_image FROM users WHERE username LIKE :username")
    result = await db.execute(query_stmt, {"username": f"%{username}%"})
    rows = result.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="No users found")

    users = [
        {
            "user_image": row.user_image,
            "username": row.username,
            "id": row.id,
            "num_found": len(rows)
        }
        for row in rows
    ]
    return users