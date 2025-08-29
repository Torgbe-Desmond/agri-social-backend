from fastapi import Query, Depends, HTTPException, status, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import uuid
from ... import schemas
from blog.database import get_async_db
from .route import postRoute
from uuid import UUID

@postRoute.post("/{post_id}/save", status_code=status.HTTP_200_OK)
async def toggle_like_saved_post(
    post_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    try:
        saved = None
        user_id = request.state.user.get("user_id")
        params = {"user_id": user_id, "post_id": str(post_id)}

        saved_post_stmt = text("""
            SELECT * FROM saved_posts WHERE user_id = :user_id AND post_id = :post_id
        """)
        result = await db.execute(saved_post_stmt, params)
        saved_post = result.fetchone()

        if saved_post:
            saved = False
            await db.execute(text("""
                DELETE FROM saved_posts WHERE user_id = :user_id AND post_id = :post_id
            """), params)
        else:
            saved = True
            await db.execute(text("""
                INSERT INTO saved_posts (post_id, user_id, created_at)
                VALUES (:post_id, :user_id, CURRENT_TIMESTAMP)
            """), params)

        await db.commit()
        return {"post_id": str(post_id), "saved": saved}

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))