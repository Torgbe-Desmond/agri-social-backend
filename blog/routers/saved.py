from fastapi import APIRouter, Form, Depends, HTTPException, status, Request,Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from datetime import datetime
import uuid

from .. import schemas
from blog.database import get_async_db
from ..utils.stored_procedure_strings import _get_saved_posts

router = APIRouter()

@router.post('/toggle-save/{post_id}', status_code=status.HTTP_200_OK)
async def toggle_save(post_id: str, request: Request, db: AsyncSession = Depends(get_async_db)):
    try:
        saved = None
        current_user = request.state.user
        user_id = current_user.get("user_id")
        params = {"user_id": user_id, "post_id": post_id}
        
        # Check if post is already saved
        saved_post_stmt = text("""
            SELECT * FROM saved_posts WHERE user_id = :user_id AND post_id = :post_id
        """)
        result = await db.execute(saved_post_stmt, params)
        saved_post = result.fetchone()

        if saved_post:
            saved = False
            delete_stmt = text("""
                DELETE FROM saved_posts WHERE user_id = :user_id AND post_id = :post_id
            """)
            await db.execute(delete_stmt, params)
        else:
            saved = True
            insert_stmt = text("""
                INSERT INTO saved_posts (post_id, user_id, created_at)
                VALUES (:post_id, :user_id, CURRENT_TIMESTAMP)
            """)
            await db.execute(insert_stmt, params)

        await db.commit()
        return {"post_id": post_id, "saved": saved}

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/saved-history', status_code=status.HTTP_200_OK, response_model=schemas.AllPost)
async def saved_history(
    request: Request,
    offset: int = Query(1, ge=1),         # Start from page 1
    limit: int = Query(10, gt=0),         # Must request at least 1 item
    db: AsyncSession = Depends(get_async_db)
):
    try:
        current_user = request.state.user
        user_id = str(current_user.get("user_id"))
        cal_offset = (offset - 1) * limit

        # 1. Count total saved posts
        count_stmt = text("SELECT COUNT(*) FROM saved_posts WHERE user_id = :user_id")
        count_result = await db.execute(count_stmt, {"user_id": user_id})
        total_count = count_result.scalar()

        # 2. Get joined post IDs
        saved_stmt = text("""
            SELECT STRING_AGG(post_id::text, ',') AS post_ids 
            FROM saved_posts 
            WHERE user_id = :user_id
        """)
        result = await db.execute(saved_stmt, {"user_id": user_id})
        joined_post_ids = result.scalar()

        if not joined_post_ids:
            return schemas.AllPost(posts=[], numb_found=0)

        # 3. Fetch detailed post data with pagination
        result = await db.execute(_get_saved_posts, {
            "PostIds": joined_post_ids,
            "offset": cal_offset,
            "limit": limit
        })

        saved_posts = result.fetchall()
        print("saved_posts",saved_posts)

        return schemas.AllPost(
            posts=[row._mapping for row in saved_posts] if saved_posts else [],
            numb_found=total_count or 0
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch saved history: {str(e)}"
        )


@router.delete('/delete-saved/{post_id}', status_code=status.HTTP_200_OK)
async def delete_saved(request:Request, post_id: str, db: AsyncSession = Depends(get_async_db)):
    try:
        current_user = request.state.user
        result = await db.execute(text("""
            DELETE FROM saved_posts WHERE user_id = :user_id AND post_id = :post_id
        # """), {"user_id": current_user.get("user_id"), "post_id": post_id})

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="No saved post to delete.")

        await db.commit()
        return {"post_id": post_id}

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# "(sqlalchemy.dialects.postgresql.asyncpg.ProgrammingError) <class 'asyncpg.exceptions.PostgresSyntaxError'>: syntax error at end of input
# [SQL: 
#             DELETE FROM saved_posts WHERE user_id = $1 AND post_id = $2
#         # ]
# [parameters: ('a83d3785-84c2-4086-8cc5-dd8cfdc9d23d', 'c345f79f-8477-47d0-b9b9-00c506638bd6')]
# (Background on this error at: https://sqlalche.me/e/20/f405)"


