
from fastapi import status,Depends, HTTPException, Request,Form,UploadFile,File
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import uuid
from . import _schema
from blog.database import get_async_db
from .route import commentRoute
from ...utils import generate_random_string
from ...utils.firebase_interactions import upload_file_to_storage,delete_file_from_storage

@commentRoute.post('/{post_id}', status_code=status.HTTP_201_CREATED)
async def add_comment(
    post_id: str,
    request: Request,
    post_owner: str = Form(...),
    has_video: Optional[int] = Form(None),
    content: str = Form(...),
    tags: Optional[str] = Form(None),    
    files: Optional[List[UploadFile]] = File(None), 
    db: AsyncSession = Depends(get_async_db)
):
    try:
        current_user = request.state.user
        video_value = has_video if has_video else 0

        # Check if post exists
        post_result = await db.execute(text("SELECT content FROM posts WHERE id = :post_id"),
                                       {"post_id": post_id})
        post = post_result.fetchone()
        if not post:
            raise HTTPException(status_code=400, detail="Post does not exist.")
        post = post._mapping

        # Check if user exists
        user_result = await db.execute(text("SELECT username FROM users WHERE id = :user_id"),
                                       {"user_id": current_user.get("user_id")})
        user = user_result.fetchone()
        if not user:
            raise HTTPException(status_code=400, detail="Unauthenticated user.")

        # Insert comment
        comment_result = await db.execute(text("""
            INSERT INTO comments (post_id, user_id, content, created_at, has_video)
            VALUES (:post_id, :user_id, :content, NOW(), :has_video)
            RETURNING id
        """), {"post_id": post_id, "user_id": current_user.get("user_id"), "content": content, "has_video": video_value})

        created_comment = comment_result.fetchone()
        comment_id = created_comment._mapping["id"]
        
        if tags:
            tag_list = tags.split(",")
            for tag in tag_list:
                await db.execute(text("""
                    INSERT INTO tags ( tag_name, created_at, comment_id, creator)
                    VALUES( :tag_name, NOW(), :comment_id, :creator)
                """), {
                    "tag_name": tag,
                    "comment_id": comment_id,
                    "creator": "user"
                })

        image_urls = []
        video_urls = []
        generated_names = []

        if files:
            for file in files:
                mimetype = file.content_type.split("/")[0]
                content_type = file.content_type
                file_bytes = await file.read()
                file_name = file.filename
                extension = file_name.split(".")[-1]
                generated_name = f"plant.disease.detection.{generate_random_string()}.{extension}"
                generated_names.append(generated_name)

                file_url = await upload_file_to_storage(current_user.get("user_id"), generated_name, file_bytes, content_type)

                if file_url:
                    if mimetype == "image":
                        await db.execute(text("""
                            INSERT INTO comment_images (comment_id, image_url, filename, user_id, generated_name)
                            VALUES (:comment_id, :image_url, :filename, :user_id, :generated_name)
                        """), {
                            "comment_id": comment_id,
                            "image_url": file_url,
                            "filename": file_name,
                            "user_id": current_user.get("user_id"),
                            "generated_name": generated_name
                        })
                        
                        image_urls.append(file_url)

                    elif mimetype == "video":
                        await db.execute(text("""
                            INSERT INTO comment_videos (comment_id, video_url, filename, user_id, generated_name)
                            VALUES (:comment_id, :video_url, :filename, :user_id, :generated_name)
                        """), {
                            "comment_id": comment_id,
                            "video_url": file_url,
                            "filename": file_name,
                            "user_id": current_user.get("user_id"),
                            "generated_name": generated_name
                        })
                        
                        video_urls.append(file_url)


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
            "images": ",".join(image_urls),
            "videos": ",".join(video_urls)
        }

    except Exception as e: 
        await db.rollback()
        if generated_names:
            for gen_name in generated_names:
                try:
                    await delete_file_from_storage(current_user.get("user_id"), gen_name)
                except Exception as cleanup_error:
                    print(f"Failed to delete uploaded file {gen_name}: {cleanup_error}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

