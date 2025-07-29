from fastapi import APIRouter, status, Form, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import uuid
from .. import schemas
from blog.database import get_async_db
from ..utils.stored_procedure_strings import _get_comments, _get_comment,_get_replies

router = APIRouter()

@router.get('/get-comments/{post_id}', status_code=status.HTTP_200_OK, response_model = schemas.AllComment)
async def get_comments(request:Request, post_id: str, db: AsyncSession = Depends(get_async_db)):
    try:
        current_user = request.state.user
        # Step 1: Get total comment count for the post
        count_stmt = text("""
            SELECT COUNT(*) 
            FROM comments
            WHERE post_id = :post_id 
        """)
        count_result = await db.execute(count_stmt, {"post_id": post_id})
        total_count = count_result.scalar()

        # Step 2: Get all comments and replies
        result = await db.execute(_get_comments, {"post_id": post_id, "current_user_id":current_user.get("user_id")})
        rows = result.fetchall()
        
        comments = [
            {
                "id": str(row.id),
                "post_id": str(row.post_id),
                "user_id": str(row.user_id),
                "likes": row.likes,
                "username": row.username,
                "content": row.content,
                "replies": row.replies,
                "created_at": row.created_at,
                "user_image": row.user_image,
                "liked":row.liked,
                "parent_id": str(row.parent_id) if row.parent_id else None,
            }
            for row in rows
        ]
         
        return schemas.AllComment(
            comments=comments if comments else [],
            numb_found=total_count or 0
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    


@router.get('/get-replies/{comment_id}', status_code=status.HTTP_200_OK, response_model = schemas.AllComment)
async def get_comments(request:Request,comment_id: str, db: AsyncSession = Depends(get_async_db)):
    try:
        current_user = request.state.user
        # Step 1: Get total comment count for the post
        count_stmt = text("""
            SELECT COUNT(*) 
            FROM comments
            WHERE parent_id = :comment_id
        """)
        count_result = await db.execute(count_stmt, {"comment_id": comment_id})
        total_count = count_result.scalar()

        # Step 2: Get all comments and replies
        result = await db.execute(_get_replies, {"comment_id": comment_id,"current_user_id":current_user.get("user_id")})
        rows = result.fetchall()
        
        comments = [
            {
                "id": str(row.id),
                "post_id": str(row.post_id),
                "user_id": str(row.user_id),
                "likes": row.likes,
                "username": row.username,
                "content": row.content,
                "replies": row.replies,
                "created_at": row.created_at,
                "user_image": row.user_image,
                "liked":row.liked,
                "parent_id": str(row.parent_id) if row.parent_id else None,
            }
            for row in rows
        ]
         
        return schemas.AllComment(
            comments=comments if comments else [],
            numb_found=total_count or 0
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/get-comment/{comment_id}', status_code=status.HTTP_200_OK)
async def get_comment(request:Request, comment_id: str, db: AsyncSession = Depends(get_async_db)):
    try:
        current_user = request.state.user
        result = await db.execute(_get_comment, {"comment_id": comment_id,"current_user_id":current_user.get("user_id")})
        row = result.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="No comment found.")

        return dict(row._mapping)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post('/toggle-comment-like/{comment_id}', status_code=status.HTTP_200_OK)
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

@router.post('/add-comment/{post_id}', status_code=status.HTTP_201_CREATED)
async def add_comment(
    post_id: str,
    request:Request,
    post_owner: str = Form(...),
    content: str = Form(...),
    db: AsyncSession = Depends(get_async_db)
):
    try:
        # Check post exists
        current_user  = request.state.user
        post_result = await db.execute(text("SELECT content FROM posts WHERE id = :post_id"),
                                       {"post_id": post_id})
        post = post_result.fetchone()
        if not post:
            raise HTTPException(status_code=400, detail="Post does not exist.")
        post = post._mapping

        # Check user exists
        user_result = await db.execute(text("SELECT username FROM users WHERE id = :user_id"),
                                       {"user_id": current_user.get("user_id")})
        user = user_result.fetchone()
        if not user:
            raise HTTPException(status_code=400, detail="Unauthenticated user.")

       # Insert a comment into the database and return its ID and creation timestamp
        comment_result = await db.execute(text("""
            INSERT INTO comments (post_id, user_id, content, created_at)
            VALUES (:post_id, :user_id, :content, NOW())
            RETURNING id, created_at
        """), {
            "post_id": post_id,
            "user_id": current_user.get("user_id"),
            "content": content
        })
        
        # Fetch the newly created comment's ID and timestamp
        created_comment = comment_result.fetchone()
        comment_id = created_comment._mapping["id"]
        created_at = created_comment._mapping["created_at"]

        # Create notification
        await db.execute(text("""
            INSERT INTO notifications (
                user_id, actor_id, type, action_id,
                entity_type, entity_id, message, is_read, created_at
            ) VALUES (
                :user_id, :actor_id, 'comment', :action_id,
                'post', :entity_id, :message, 0, NOW()
            )
            """), {
            "user_id": post_owner,
            "actor_id": current_user.get("user_id"),
            "action_id": str(comment_id), 
            "entity_id": str(post_id),
            "message": post.content
        })

        await db.commit()
        return {
            "id": comment_id,
            "post_id": post_id,
            "user_id": current_user.get("user_id"),
            "content": content,
            "created_at":created_at
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post('/add-reply-comment/{comment_id}', status_code=status.HTTP_201_CREATED)
async def add_reply_comment(
    comment_id: str,
    request:Request,
    post_id: str = Form(...),
    post_owner: str = Form(...),
    content: str = Form(...),
    db: AsyncSession = Depends(get_async_db)
):
    try:
        current_user = request.state.user
        # Check if parent comment exists
        check_comment = await db.execute(text(
            "SELECT content FROM comments WHERE id = :comment_id"
        ), {"comment_id": comment_id})
        parent_comment = check_comment.fetchone()
        if not parent_comment:
            raise HTTPException(status_code=400, detail="Comment does not exist.")

        # Check if user exists
        user_result = await db.execute(text(
            "SELECT username FROM users WHERE id = :user_id"
        ), {"user_id": current_user.get("user_id")})
        user = user_result.fetchone()
        if not user:
            raise HTTPException(status_code=400, detail="Unauthenticated user.")

        # Insert the reply comment and get its ID
        comment_result = await db.execute(text("""
            INSERT INTO comments ( post_id, user_id, content, parent_id, created_at)
            VALUES ( :post_id, :user_id, :content, :parent_id, NOW())
            RETURNING id
        """), {
            "post_id": post_id,
            "user_id": current_user.get("user_id"),
            "content": content,
            "parent_id": comment_id  
        })
        created_comment = comment_result.fetchone()
        new_comment_id = created_comment._mapping["id"]

        # Create notification for the post owner
        await db.execute(text("""
            INSERT INTO notifications (
                user_id, actor_id, type, action_id,
                entity_type, entity_id, message, is_read, created_at
            ) VALUES (
                :user_id, :actor_id, 'reply', :action_id,
                'comment', :entity_id, :message, 0, NOW()
            )
        """), {
            "user_id": post_owner,
            "actor_id": current_user.get("user_id"),
            "action_id": str(new_comment_id),
            "entity_id": str(comment_id),
            "message": parent_comment.content
        })

        await db.commit()

        return {
            "id": new_comment_id,
            "post_id": post_id,
            "user_id": current_user.get("user_id"),
            "content": content,
            "parent_id": comment_id
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
    
    
    
    
    
    
    
    
    
#     "2 validation errors for AllComment
# comments.5.parent_id
#   Input should be a valid string [type=string_type, input_value=UUID('3ad0e888-6a30-497b-8672-270995f6c773'), input_type=UUID]
#     For further information visit https://errors.pydantic.dev/2.11/v/string_type
# comments.6.parent_id
#   Input should be a valid string [type=string_type, input_value=UUID('3ad0e888-6a30-497b-8672-270995f6c773'), input_type=UUID]
#     For further information visit https://errors.pydantic.dev/2.11/v/string_type"