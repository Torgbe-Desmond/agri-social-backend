from fastapi import status, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from . import _schema
from blog.database import get_async_db
from .route import commentRoute


@commentRoute.get('/{comment_id}/replies', status_code=status.HTTP_200_OK, response_model = _schema.AllComment)
async def get_replies(comment_id: str,request:Request, db: AsyncSession = Depends(get_async_db)):
    try:
        current_user = request.state.user
        # Step 1: Get total comment count for the post
        current_user = request.state.user
        count_stmt = text("""
            SELECT COUNT(*) 
            FROM comments
            WHERE parent_id = :comment_id
        """)
        count_result = await db.execute(count_stmt, {"comment_id": comment_id})
        total_count = count_result.scalar()

        # Step 2: Get all comments and replies
        result = await db.execute(text("""
            SELECT 
                 c.id,
                 c.post_id,
                 c.user_id,
                 c.content,
                 c.created_at,
                 COALESCE(u.user_image, '') AS user_image,
                 c.parent_id,
                  EXISTS (
                     SELECT 1 
                     FROM comment_likes  
                     WHERE comment_id = c.id::uuid
                 ) AS liked , 
                 COALESCE((
                     SELECT STRING_AGG(image_url, ',') 
                     FROM comment_images 
                     WHERE comment_id = c.id::uuid
                    ), '') AS images,
                 COALESCE((
                     SELECT STRING_AGG(video_url, ',') 
                     FROM comment_videos 
                     WHERE comment_id = c.id::uuid
                    ), '') AS videos,  
                 COALESCE((
                     SELECT STRING_AGG(tag_name, ',') 
                     FROM tags 
                     WHERE comment_id = c.id::uuid
                 ), '') AS tags,
                 (SELECT COUNT(*) FROM comments WHERE parent_id = c.id) AS replies,
                 (SELECT COUNT(*) FROM comment_likes WHERE comment_id = c.id) AS likes,
                 u.username
             FROM comments c
             LEFT JOIN users u ON u.id = c.user_id
             WHERE c.parent_id = :comment_id
             ORDER BY c.created_at ASC"""), 
            {
                "comment_id": comment_id,
                "current_user_id":current_user.get('user_id')
            })
        rows = result.fetchall()
        
        comments = [
            {
                "id": str(row.id),
                "post_id": str(row.post_id),
                "user_id": str(row.user_id),
                "likes": row.likes,
                "username": row.username,
                "videos":row.videos,
                "images":row.images,
                "content": row.content,
                "replies": row.replies,
                "created_at": row.created_at,
                "user_image": row.user_image,
                "liked":row.liked,
                "parent_id": str(row.parent_id) if row.parent_id else None,
            }
            for row in rows
        ]
                 
        return _schema.AllComment(
            comments=comments if comments else [],
            numb_found=total_count or 0
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))