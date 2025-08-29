
from fastapi import status,Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import uuid
from . import _schema
from blog.database import get_async_db
from .route import commentRoute

@commentRoute.get('/{comment_id}/comment', status_code=status.HTTP_200_OK)
async def get_comment(comment_id: str,request:Request, db: AsyncSession = Depends(get_async_db)):
    try:
        current_user = request.state.user
        result = await db.execute(text("""
        SELECT 
         c.id,
         c.post_id,
         c.user_id,
         c.content,
         c.created_at,
         c.has_video,
         COALESCE(u.user_image, '') AS user_image,
         EXISTS (
             SELECT 1 
             FROM comment_likes  
             WHERE comment_id = c.id AND user_id = :current_user_id
         ) AS liked,
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
         u.username,
         c.parent_id,
         (SELECT COUNT(*) FROM comments WHERE parent_id = c.id) AS replies,
         (SELECT COUNT(*) FROM comment_likes WHERE comment_id = c.id) AS likes

        FROM comments c
        LEFT JOIN users u ON u.id = c.user_id
        WHERE c.id = :comment_id;"""), 
        {
            "comment_id": comment_id,
            "current_user_id":current_user.get('user_id')
        })
        row = result.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="No comment found.")

        return dict(row._mapping)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))