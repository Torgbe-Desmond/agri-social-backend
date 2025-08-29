from fastapi import Query, Depends, HTTPException, status, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import uuid
from ... import schemas
from blog.database import get_async_db
from .route import postRoute

@postRoute.get('/{post_id}', response_model=schemas.GetAllPost)
async def get_post(post_id: str,request:Request,db: AsyncSession = Depends(get_async_db)):
    try:
        current_user = request.state.user
        result = await db.execute(text("""
           SELECT 
             p.id AS post_id,
             p.content,
             p.created_at,
             p.user_id,
             p.has_video,
         
             COALESCE(u.user_image, '') AS user_image,
             u.username,
         
             (SELECT COUNT(*) FROM post_likes WHERE post_id = p.id) AS likes,
         
             EXISTS (
                 SELECT 1 
                 FROM post_likes  
                 WHERE post_id = p.id AND user_id = :current_user_id
             ) AS liked, 
         
             EXISTS (
                 SELECT 1 
                 FROM saved_posts  
                 WHERE post_id = p.id AND user_id = :current_user_id
             ) AS saved, 
         
             (SELECT COUNT(*) FROM saved_posts WHERE post_id = p.id) AS saves,
         
             (SELECT COUNT(*) FROM comments WHERE post_id = p.id AND parent_id IS NULL) AS comments,
         
             (SELECT image_url FROM post_images WHERE post_id = p.id LIMIT 1) AS images,
         
             COALESCE((
                 SELECT STRING_AGG(tag_name, ',') 
                 FROM tags 
                 WHERE post_id = p.id
             ), '') AS tags,
         
             (SELECT video_url FROM post_videos WHERE post_id = p.id LIMIT 1) AS videos
         
            FROM posts p
            JOIN users u ON u.id = p.user_id
            WHERE p.id = :currentPostId;
            """), 
            {
                "currentPostId": post_id, 
                "current_user_id":current_user.get('user_id')
            })
        post = result.fetchone()

        if not post:
            raise HTTPException(status_code=404, detail="No recommended posts found.")

        return post._mapping

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    