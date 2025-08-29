from fastapi import Query, Depends, HTTPException, status, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import uuid
from ... import schemas
from blog.database import get_async_db
from .route import postRoute
from uuid import UUID

@postRoute.delete("/{post_id}/unsave", status_code=status.HTTP_200_OK)
async def delete_saved(
    request: Request,
    post_id: UUID, 
    db: AsyncSession = Depends(get_async_db)
):
    try:
        user_id = request.state.user.get("user_id")
        result = await db.execute(text("""
            DELETE FROM saved_posts WHERE user_id = :user_id AND post_id = :post_id
        """), {"user_id": user_id, "post_id": str(post_id)})

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="No saved post to delete.")

        await db.commit()
        return {"post_id": str(post_id)}


    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
