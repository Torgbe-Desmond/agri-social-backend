
from fastapi import Query, Depends, HTTPException, status, Request, Form, UploadFile, File
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import uuid
from ... import schemas
from blog.database import get_async_db
from .route import postRoute

@postRoute.get("/saved", status_code=status.HTTP_200_OK, response_model=schemas.AllPost)
async def saved_post_history(
    request: Request,
    offset: int = Query(1, ge=1),
    limit: int = Query(10, gt=0),
    db: AsyncSession = Depends(get_async_db)
):
    try:
        current_user = request.state.user
        user_id = str(current_user.get("user_id"))
        cal_offset = (offset - 1) * limit

        count_stmt = text("SELECT COUNT(*) FROM saved_posts WHERE user_id = :user_id")
        count_result = await db.execute(count_stmt, {"user_id": user_id})
        total_count = count_result.scalar()

        saved_stmt = text("""
            SELECT STRING_AGG(post_id::text, ',') AS post_ids 
            FROM saved_posts 
            WHERE user_id = :user_id
        """)
        result = await db.execute(saved_stmt, {"user_id": user_id})
        joined_post_ids = result.scalar()

        if not joined_post_ids:
            return schemas.AllPost(posts=[], numb_found=0)

        result = await db.execute( text("""
        SELECT 
            p.id AS post_id,
            p.content,
            p.created_at,
            p.user_id,
            p.has_video,
            COALESCE(u.user_image, '') AS user_image,
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
            (SELECT COUNT(*) FROM post_likes WHERE post_id = p.id) AS likes,
            (SELECT COUNT(*) FROM saved_posts WHERE post_id = p.id) AS saves,
            (SELECT COUNT(*) FROM comments WHERE post_id = p.id) AS comments,
            (SELECT image_url FROM post_images WHERE post_id = p.id LIMIT 1) AS images,
            (SELECT video_url FROM post_videos WHERE post_id = p.id LIMIT 1) AS videos,
            u.username
        FROM posts p
        JOIN users u ON u.id = p.user_id
        WHERE p.id IN (
            SELECT unnest(string_to_array(:PostIds, ',')::uuid[])
        )
        ORDER BY p.created_at DESC
        OFFSET :offset
        LIMIT :limit;
        """), {
            "PostIds": joined_post_ids,
            "offset": cal_offset,
            "limit": limit,
            "current_user_id":user_id
        })

        saved_posts = result.fetchall()

        return schemas.AllPost(
            posts=[row._mapping for row in saved_posts],
            numb_found=total_count or 0
        )

    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch saved history: {str(e)}"
        )