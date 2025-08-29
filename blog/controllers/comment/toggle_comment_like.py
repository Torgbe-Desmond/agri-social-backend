
from fastapi import status,Depends, HTTPException, Request,Form
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import uuid
from . import _schema
from blog.database import get_async_db
from .route import commentRoute


@commentRoute.post('/{comment_id}/like', status_code=status.HTTP_200_OK)
async def toggle_comment_like(
    comment_id: str,
    request: Request,
    post_owner: str = Form(...),
    db: AsyncSession = Depends(get_async_db)
):
    try:
        current_user = request.state.user

        # Check if the comment exists
        result = await db.execute(
            text("SELECT content FROM comments WHERE id = :comment_id"),
            {"comment_id": comment_id}
        )
        comment = result.fetchone()
        if not comment:
            raise HTTPException(status_code=404, detail="Comment not found.")

        # Check if the current user already liked the comment
        like_check = await db.execute(
            text("SELECT 1 FROM comment_likes WHERE user_id = :user_id AND comment_id = :comment_id"),
            {"user_id": current_user.get("user_id"), "comment_id": comment_id}
        )
        liked = like_check.fetchone()

        if liked:
            # Remove the like and related notification
            await db.execute(
                text("DELETE FROM comment_likes WHERE user_id = :user_id AND comment_id = :comment_id"),
                {"user_id": current_user.get("user_id"), "comment_id": comment_id}
            )
            await db.execute(
                text("""
                    DELETE FROM notifications
                    WHERE actor_id = :user_id AND entity_type = 'comment'
                    AND entity_id = :comment_id AND type = 'like'
                """),
                {"user_id": current_user.get("user_id"), "comment_id": comment_id}
            )
            liked = False
        else:
            # Insert the like
            await db.execute(
                text("""
                    INSERT INTO comment_likes (comment_id, user_id, created_at)
                    VALUES (:comment_id, :user_id, NOW())
                """),
                {"comment_id": comment_id, "user_id": current_user.get("user_id")}
            )

            # Insert a notification for the like
            await db.execute(text("""
                INSERT INTO notifications (
                    user_id, actor_id, type, entity_type, entity_id, message, is_read, created_at
                ) VALUES (
                    :user_id, :actor_id, 'like', 'comment', :entity_id, :message, 0, NOW()
                )
            """), {
                "user_id": post_owner,
                "actor_id": current_user.get("user_id"),
                "entity_id": comment_id,
                "message": comment.content,
            })
            liked = True

        await db.commit()
        return {"comment_id": comment_id, "liked": liked}

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")