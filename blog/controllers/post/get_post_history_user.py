from fastapi import Query, Depends, HTTPException, status, Request, Form, UploadFile, File
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import uuid
from ... import schemas
from blog.database import get_async_db
from .route import postRoute

@postRoute.get('/{user_id}/posts', response_model=schemas.AllPost)
async def get_post_history_user(
    user_id, 
    offset: int = Query(1, ge=1),         
    limit: int = Query(10, gt=0),        
    db: AsyncSession = Depends(get_async_db)):
    try:
                
        cal_offset = (offset - 1) * limit
        # Count the number of posts
        count_stmt = text("""
            SELECT COUNT(*)
            FROM posts p
            WHERE p.user_id = :user_id
        """)

        count_result = await db.execute(count_stmt, {"user_id": user_id})
        total_count = count_result.scalar()

        # Fetch post history
        result = await db.execute( text("""
            SELECT 
            p.id AS post_id,
            p.content,
            p.created_at,
            p.user_id,
            p.has_video,
            COALESCE(u.user_image, '') AS user_image,
            (SELECT COUNT(*) FROM post_likes WHERE post_id = p.id) AS likes,
            (SELECT COUNT(*) FROM saved_posts WHERE post_id = p.id) AS saves,
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
            (SELECT COUNT(*) 
             FROM comments 
             WHERE post_id = p.id AND parent_id IS NULL
            ) AS comments,
            COALESCE((
                SELECT STRING_AGG(image_url, ',') 
                FROM post_images 
                WHERE post_id = p.id
            ), '') AS images,
            COALESCE((
                SELECT STRING_AGG(tag_name, ',') 
                FROM tags 
                WHERE post_id = p.id
            ), '') AS tags,
            COALESCE((
                SELECT STRING_AGG(video_url, ',') 
                FROM post_videos 
                WHERE post_id = p.id
            ), '') AS videos,
            u.username
            FROM posts p
            JOIN users u ON u.id = p.user_id
            WHERE p.user_id = :user_id
            ORDER BY p.created_at DESC
            OFFSET :offset
            LIMIT :limit;

            """), 
            {
                "user_id": user_id, 
                "offset": cal_offset,
                "limit": limit , 
                "current_user_id":user_id
            })
        posts = result.fetchall()

        return schemas.AllPost(
            posts=[row._mapping for row in posts] if posts else [],
            numb_found=total_count or 0
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching post history: {str(e)}")
