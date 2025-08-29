
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

@commentRoute.post('/{comment_id}/replies', status_code=status.HTTP_201_CREATED)
async def add_reply_comment(
    comment_id: str,
    request: Request,
    post_id: str = Form(...),
    tags: Optional[str] = Form(None),    
    has_video: Optional[int] = Form(None),
    post_owner: str = Form(...),
    files: List[UploadFile] = File(None), 
    content: str = Form(...),
    db: AsyncSession = Depends(get_async_db)
):
    # ✅ Ensure these are defined before try block
    generated_names = []
    image_urls = []
    video_urls = []

    try:
        current_user = request.state.user
        video_value = int(has_video) if has_video else 0

        # ✅ Check if parent comment exists
        check_comment = await db.execute(text(
            "SELECT content FROM comments WHERE id = :comment_id"
        ), {"comment_id": comment_id})
        parent_comment = check_comment.fetchone()
        if not parent_comment:
            raise HTTPException(status_code=400, detail="Comment does not exist.")

        # ✅ Check if user exists
        user_result = await db.execute(text(
            "SELECT username FROM users WHERE id = :user_id"
        ), {"user_id": current_user.get("user_id")})
        user = user_result.fetchone()
        if not user:
            raise HTTPException(status_code=400, detail="Unauthenticated user.")

        # ✅ Insert the reply comment
        comment_result = await db.execute(text("""
            INSERT INTO comments (post_id, user_id, content, parent_id, created_at, has_video)
            VALUES (:post_id, :user_id, :content, :parent_id, NOW(), :has_video)
            RETURNING id, created_at
        """), {
            "post_id": post_id,
            "user_id": current_user.get("user_id"),
            "content": content,
            "parent_id": comment_id,
            "has_video": video_value
        })

        created_comment = comment_result.fetchone()
        new_comment_id = created_comment._mapping["id"]
        created_at = created_comment._mapping["created_at"]

        # ✅ Handle tags
        if tags:
            tag_list = tags.split(",")
            for tag in tag_list:
                await db.execute(text("""
                    INSERT INTO tags (tag_name, created_at, comment_id, creator)
                    VALUES (:tag_name, NOW(), :comment_id, :creator)
                """), {
                    "tag_name": tag.strip(),
                    "comment_id": new_comment_id,
                    "creator": "user"
                })

        # ✅ Handle file uploads (images/videos)
        if files:
            for file in files:
                mimetype = file.content_type.split("/")[0]
                content_type = file.content_type
                file_bytes = await file.read()
                file_name = file.filename
                extension = file_name.split(".")[-1]
                generated_name = f"plant.disease.detection.{generate_random_string()}.{extension}"

                file_url = await upload_file_to_storage(current_user.get("user_id"), generated_name, file_bytes, content_type)

                if file_url:
                    generated_names.append(generated_name)

                    if mimetype == "image":
                        await db.execute(text("""
                            INSERT INTO comment_images (comment_id, image_url, filename, user_id, generated_name)
                            VALUES (:comment_id, :image_url, :filename, :user_id, :generated_name)
                        """), {
                            "comment_id": new_comment_id,
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
                            "comment_id": new_comment_id,
                            "video_url": file_url,
                            "filename": file_name,
                            "user_id": current_user.get("user_id"),
                            "generated_name": generated_name
                        })
                        video_urls.append(file_url)

        # ✅ Create notification
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
            "parent_id": comment_id,
            "images": ",".join(image_urls),
            "videos": ",".join(video_urls),
            "created_at": created_at
        }

    except Exception as e:
        await db.rollback()

        # ✅ Cleanup uploaded files on error
        if generated_names:
            for gen_name in generated_names:
                try:
                    await delete_file_from_storage(current_user.get("user_id"), gen_name)
                except Exception as cleanup_error:
                    print(f"Failed to delete uploaded file {gen_name}: {cleanup_error}")

        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
