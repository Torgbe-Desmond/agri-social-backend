from fastapi import APIRouter, Form, Depends, HTTPException, status
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
async def toggle_save(post_id: str, user_id: str = Form(...), db: AsyncSession = Depends(get_async_db)):
    try:
        saved = None

        # Check if the user already saved this specific post
        saved_post_stmt = text("""
            SELECT * FROM saved_posts WHERE user_id = :user_id AND post_id = :post_id
        """)
        result = await db.execute(saved_post_stmt, {"user_id": user_id, "post_id": post_id})
        saved_post = result.fetchone()

        if saved_post:
            saved = False
            delete_stmt = text("""
                DELETE FROM saved_posts WHERE user_id = :user_id AND post_id = :post_id
            """)
            await db.execute(delete_stmt, {"user_id": user_id, "post_id": post_id})
        else:
            saved = True
            insert_stmt = text("""
                INSERT INTO saved_posts (post_id, user_id, created_at)
                VALUES ( :post_id, :user_id, CURRENT_TIMESTAMP)
            """)
            
            await db.execute(insert_stmt, {
                "post_id": post_id,
                "user_id": user_id
            })
           

        await db.commit()
        return {"post_id": post_id, "saved": saved}

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/saved-history/{user_id}', status_code=status.HTTP_200_OK, response_model=List[schemas.GetAllPost])
async def saved_history(user_id: str, db: AsyncSession = Depends(get_async_db)):
    try:
        saved_stmt = text("""
            SELECT STRING_AGG(post_id::text, ',') AS post_ids FROM saved_posts WHERE user_id = :user_id
        """)
        result = await db.execute(saved_stmt, {"user_id": user_id})
        joined_post_ids = result.scalar()

        if not joined_post_ids:
            raise HTTPException(status_code=404, detail="No saved posts found.")

        # Call stored procedure with post IDs
        result = await db.execute(_get_saved_posts, {"PostIds": joined_post_ids})
        saved_posts = result.fetchall()

        return saved_posts

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.delete('/delete-saved/{user_id}/one/{post_id}', status_code=status.HTTP_200_OK)
async def delete_saved(user_id: str, post_id: str, db: AsyncSession = Depends(get_async_db)):
    try:
        result = await db.execute(text("""
            DELETE FROM saved_posts WHERE user_id = :user_id AND post_id = :post_id
        """), {"user_id": user_id, "post_id": post_id})

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="No saved post to delete.")

        await db.commit()
        return {"post_id": post_id}

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
