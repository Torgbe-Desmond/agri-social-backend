from fastapi import APIRouter, status, Form, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import uuid
from .. import schemas
from blog.database import get_async_db
from ..utils.stored_procedure_strings import _get_comments, _get_comment

router = APIRouter()

@router.get('/get-comments/{post_id}', status_code=status.HTTP_200_OK,response_model=schemas.AllComment)
async def get_comments(post_id: str, db: AsyncSession = Depends(get_async_db)):
    try:
        
        count_stmt = text("""  
            SELECT COUNT(*) 
            FROM comments c
            LEFT JOIN users u ON u.id = c.user_id
            WHERE c.post_id = :ParentOrPostId OR c.parent_id = :ParentOrPostId
            ORDER BY c.created_at ASC
        """)
        
        result = await db.execute(count_stmt,{"ParentOrPostId": post_id})
        total_count = result.scalar()
        
        result = await db.execute(_get_comments, {"ParentOrPostId": post_id})
        results = result.fetchall()
        
        if result:    
            return schemas.AllComment(comments=results,numb_found=total_count)

        return schemas.AllComment(comments=[],numb_found=0)

        # comments = []
        # for row in results:
        #     comments.append({
        #         "id": row.id,
        #         "post_id": row.post_id,
        #         "user_id": row.user_id,
        #         "likes": row.likes,
        #         "username": row.username,
        #         "content": row.content,
        #         "replies": row.replies,
        #         "created_at": row.created_at,
        #         "user_image": row.user_image,
        #         "parent_id": row.parent_id
        #     })
       
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/get-comment/{comment_id}', status_code=status.HTTP_200_OK)
async def get_comment(comment_id: str, db: AsyncSession = Depends(get_async_db)):
    try:
        result = await db.execute(_get_comment, {"comment_id": comment_id})
        row = result.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="No comment found.")

        return dict(row._mapping)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/toggle-comment-like/{comment_id}', status_code=status.HTTP_200_OK)
async def toggle_comment_like(
    comment_id: str,
    request:Request,
    post_owner: str = Form(...),
    db: AsyncSession = Depends(get_async_db)
):
    try:
        current_user = request.state.user
        result = await db.execute(text("SELECT content FROM comments WHERE id = :comment_id"),
                                  {"comment_id": comment_id})
        comment = result.fetchone()
        if not comment:
            raise HTTPException(status_code=404, detail="Comment not found.")

        like_check = await db.execute(text("SELECT 1 FROM comment_likes WHERE user_id = :user_id AND comment_id = :comment_id"),
                                      {"user_id": current_user.get("user_id"), "comment_id": comment_id})
        liked = like_check.fetchone()

        if liked:
            await db.execute(text("DELETE FROM comment_likes WHERE user_id = :user_id AND comment_id = :comment_id"),
                             {"user_id": current_user.get("user_id"), "comment_id": comment_id})
            await db.execute(text("""
                DELETE FROM notifications
                WHERE actor_id = :user_id AND entity_type = 'comment' AND entity_id = :comment_id AND type = 'like'
            """), {"user_id": current_user.get("user_id"), "comment_id": comment_id})
            liked = False
        else:
            await db.execute(text("""
                INSERT INTO comment_likes (id, comment_id, user_id, created_at)
                VALUES (:id, :comment_id, :user_id, GETDATE())
            """), {"comment_id": comment_id, "user_id": current_user.get("user_id")})

            await db.execute(text("""
                INSERT INTO notifications (
                    id, user_id, actor_id, type, entity_type, entity_id, message, is_read, created_at
                ) VALUES (
                    :id, :user_id, :actor_id, 'like', 'comment', :entity_id, :message, 0, GETDATE()
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

        # Insert comment with RETURNING
        comment_result = await db.execute(text("""
            INSERT INTO comments (post_id, user_id, content, created_at)
            VALUES (:post_id, :user_id, :content, NOW())
            RETURNING id
        """), {"post_id": post_id, "user_id": current_user.get("user_id"), "content": content})

        created_comment = comment_result.fetchone()
        comment_id = created_comment._mapping["id"]

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
            "content": content
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
    
    
    
    
    
    
    