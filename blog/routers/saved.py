from fastapi import APIRouter, Form, Depends, HTTPException, status, Request, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from datetime import datetime
from uuid import UUID

from .. import schemas
from blog.database import get_async_db
from ..utils.stored_procedure_strings import _get_saved_posts

router = APIRouter()

# 🔒 1. This must be declared BEFORE any /posts/{post_id} route
@router.get("/saves/saved", status_code=status.HTTP_200_OK, response_model=schemas.AllPost)
async def saved_history(
    request: Request,
    offset: int = Query(1, ge=1),
    limit: int = Query(10, gt=0),
    db: AsyncSession = Depends(get_async_db)
):
    try:
        current_user = request.state.user
        user_id = str(current_user.get("user_id"))
        cal_offset = (offset - 1) * limit

        # Count total saved
        count_stmt = text("SELECT COUNT(*) FROM saved_posts WHERE user_id = :user_id")
        count_result = await db.execute(count_stmt, {"user_id": user_id})
        total_count = count_result.scalar()

        # Get saved post IDs
        saved_stmt = text("""
            SELECT STRING_AGG(post_id::text, ',') AS post_ids 
            FROM saved_posts 
            WHERE user_id = :user_id
        """)
        result = await db.execute(saved_stmt, {"user_id": user_id})
        joined_post_ids = result.scalar()

        if not joined_post_ids:
            return schemas.AllPost(posts=[], numb_found=0)

        result = await db.execute(_get_saved_posts, {
            "PostIds": joined_post_ids,
            "offset": cal_offset,
            "limit": limit
        })

        saved_posts = result.fetchall()

        return schemas.AllPost(
            posts=[row._mapping for row in saved_posts],
            numb_found=total_count or 0
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch saved history: {str(e)}"
        )

# ✅ 2. These come AFTER the static route
@router.post("/saves/{post_id}/save", status_code=status.HTTP_200_OK)
async def toggle_save(
    post_id: UUID,  # 🔒 Accept only valid UUIDs
    request: Request,
    db: AsyncSession = Depends(get_async_db)
):
    try:
        saved = None
        user_id = request.state.user.get("user_id")
        params = {"user_id": user_id, "post_id": str(post_id)}

        # Check if post is already saved
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

@router.delete("/saves/{post_id}/unsave", status_code=status.HTTP_200_OK)
async def delete_saved(
    request: Request,
    post_id: UUID,  # 🔒 Accept only valid UUIDs
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
