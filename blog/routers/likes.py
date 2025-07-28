from fastapi import APIRouter,Request
from fastapi import status,Form
from .. import schemas
from sqlalchemy import text
from fastapi import Depends
from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from blog.database import get_db,get_async_db
from .. utils.stored_procedure_strings import _get_recommeneded_post


router = APIRouter()


@router.post('/toggle-like/{post_id}', status_code=status.HTTP_200_OK)
async def toggle_like(
    request: Request,
    post_id: str,
    post_owner: str = Form(...),
    db: AsyncSession = Depends(get_async_db)
):
    try:
        from ..socket_manager import sio, getSocket
        current_user = request.state.user
        like_id = None
        notification_id = None
        post_owner_id = None

        # Check if already liked
        result = await db.execute(text("""
            SELECT 1 FROM post_likes WHERE user_id = :user_id AND post_id = :post_id
        """), {
            "user_id": current_user.get("user_id"),
            "post_id": post_id
        })
        existing_like = result.fetchone()

        # Get post content and owner
        post_row = await db.execute(text("""
            SELECT content, user_id FROM posts WHERE id = :post_id
        """), {
            "post_id": post_id
        })
        row = post_row.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Post not found")

        post_content = row.content or ""
        post_owner_id = row.user_id

        if existing_like:
            # Unlike
            await db.execute(text("""
                DELETE FROM post_likes WHERE user_id = :user_id AND post_id = :post_id
            """), {
                "user_id": current_user.get("user_id"),
                "post_id": post_id
            })

            await db.execute(text("""
                DELETE FROM notifications 
                WHERE entity_id = :post_id AND actor_id = :user_id AND type = 'like'
            """), {
                "post_id": post_id,
                "user_id": current_user.get("user_id")
            })

            liked = False
        else:
            # Like and get inserted post_like ID
            insert_like = await db.execute(text("""
                INSERT INTO post_likes (post_id, user_id, created_at)
                VALUES (:post_id, :user_id, CURRENT_TIMESTAMP)
                RETURNING id
            """), {
                "post_id": post_id,
                "user_id": current_user.get("user_id"),
            })
            like_row = insert_like.fetchone()
            like_id = like_row.id if like_row else None

            # Insert notification
            insert_notif = await db.execute(text("""
                INSERT INTO notifications (
                    user_id, actor_id, type, entity_type, entity_id,
                    message, is_read, created_at
                ) VALUES (
                    :user_id, :actor_id, :type, :entity_type, :entity_id,
                    :message, :is_read, CURRENT_TIMESTAMP
                )
                RETURNING id
            """), {
                "user_id": post_owner,
                "actor_id": current_user.get("user_id"),
                "type": "like",
                "entity_type": "post",
                "entity_id": post_id,
                "message": post_content,
                "is_read": 0,
            })
            notif_row = insert_notif.fetchone()
            notification_id = notif_row.id if notif_row else None

            liked = True

        # ✅ Emit to the Socket.IO group (room)
        sid = getSocket(str(current_user.get("user_id"))) 
        await sio.emit("foot_notifications", {
            "user_id": str(post_owner_id),
            "entity_type": "post",
            "type": "like",
            "entity_id": post_id,
            "liked": liked
        }, room="post_footer_notifications",skip_sid=sid)  

        await db.commit()

        return {
            "post_id": post_id,
            "liked": liked,
            "like_id": like_id,
            "notification_id": notification_id if liked else None
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))




@router.get('/like-history/{user_id}', status_code=status.HTTP_200_OK, response_model=List[schemas.GetAllPost])
async def like_history( request:Request, db: AsyncSession = Depends(get_async_db)):
    try:
        # Get liked post IDs
        current_user = request.state.user
        likes_stmt = text("""SELECT STRING_AGG(post_id, ',') AS post_ids FROM post_likes WHERE user_id = :user_id""")
        result = await db.execute(likes_stmt, {"user_id": current_user.get("user_id")})
        post_ids_row = result.fetchone()
        post_ids_str = post_ids_row.post_ids if post_ids_row and post_ids_row.post_ids else ""

        if post_ids_str:
            recommended_posts_result = await db.execute(_get_recommeneded_post, {"PostIds": post_ids_str})
            posts = recommended_posts_result.fetchall()

            return [dict(row._mapping) for row in posts]
        else:
            raise HTTPException(status_code=404, detail="No liked posts found.")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

