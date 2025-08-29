from fastapi import Query, Depends, HTTPException, status, Request, Form, UploadFile, File
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import uuid
from ... import schemas
from blog.database import get_async_db
from ...utils import generate_random_string
from ...utils.firebase_interactions import upload_file_to_storage,delete_file_from_storage
from .route import postRoute


@postRoute.post('/', status_code=status.HTTP_201_CREATED, response_model=schemas.GetAllPost)
async def create_post(
    request: Request,
    content: str = Form(...),
    has_video: Optional[int] = Form(None),
    tags: Optional[str] = Form(None),
    files: Optional[List[UploadFile]] = File(None),
    db: AsyncSession = Depends(get_async_db)
):
    uploaded_files = []

    try:
        current_user = request.state.user
        video_value = has_video if has_video else 0

        # Insert post
        post_result = await db.execute(text("""
            INSERT INTO posts (user_id, content, has_video)
            VALUES (:user_id, :content, :has_video)
            RETURNING id
        """), {
            "user_id": current_user.get("user_id"),
            "content": content,
            "has_video": video_value
        })

        create_post = post_result.fetchone()
        post_id = create_post._mapping["id"]

        # Handle tags
        if tags:
            tag_list = tags.split(",")
            for tag in tag_list:
                await db.execute(text("""
                    INSERT INTO tags (tag_name, created_at, post_id, creator)
                    VALUES (:tag_name, NOW(), :post_id, :creator)
                """), {
                    "tag_name": tag.strip(),
                    "post_id": post_id,
                    "creator": "user"
                })

        # Handle multiple file uploads
        if files:
            for file in files:
                mimetype = file.content_type.split("/")[0]
                content_type = file.content_type
                file_bytes = await file.read()
                file_name = file.filename
                extension = file_name.split(".")[-1]
                generated_name = f"plant.disease.detection.{generate_random_string()}.{extension}"

                file_url = await upload_file_to_storage(
                    current_user.get("user_id"),
                    generated_name,
                    file_bytes,
                    content_type
                )

                if file_url:
                    uploaded_files.append((file_name, current_user.get("user_id")))

                    if mimetype == "image":
                        await db.execute(text("""
                            INSERT INTO post_images (post_id, image_url, filename, user_id, generated_name)
                            VALUES (:post_id, :image_url, :filename, :user_id, :generated_name)
                        """), {
                            "post_id": post_id,
                            "image_url": file_url,
                            "filename": file_name,
                            "user_id": current_user.get("user_id"),
                            "generated_name": generated_name
                        })

                    elif mimetype == "video":
                        await db.execute(text("""
                            INSERT INTO post_videos (post_id, video_url, filename, user_id, generated_name)
                            VALUES (:post_id, :video_url, :filename, :user_id, :generated_name)
                        """), {
                            "post_id": post_id,
                            "video_url": file_url,
                            "filename": file_name,
                            "user_id": current_user.get("user_id"),
                            "generated_name": generated_name
                        })

        await db.commit()

        # Fetch and return the newly created post using existing query
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
            {"currentPostId": str(post_id),"current_user_id":current_user.get("user_id")}
        )
        created_post = result.fetchone()

        return schemas.GetAllPost(
            post_id=created_post.post_id,
            content=created_post.content,
            created_at=created_post.created_at,
            likes=created_post.likes,
            saved=created_post.saved,
            user_id=created_post.user_id,
            has_video=created_post.has_video,
            comments=created_post.comments,
            username=created_post.username,
            images=created_post.images,
            tags=created_post.tags,
            videos=created_post.videos,
            user_image=created_post.user_image,
        )

    except Exception as e:
        await db.rollback()
        # Cleanup uploaded files if error occurs
        for filename, user_id in uploaded_files:
            await delete_file_from_storage(user_id, filename)
        raise HTTPException(status_code=500, detail=str(e))
