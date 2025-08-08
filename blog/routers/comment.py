from fastapi import APIRouter, status, Form, Depends, HTTPException, Request,UploadFile, File
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import uuid
from .. import schemas
from blog.database import get_async_db
from ..utils.stored_procedure_strings import _get_comments, _get_comment,_get_replies
from ..utils import generate_random_string
from ..utils.firebase_interactions import upload_file_to_storage, delete_file_from_storage


router = APIRouter()

@router.get('/comments/{post_id}', status_code=status.HTTP_200_OK, response_model = schemas.AllComment)
async def get_comments(post_id: str,request:Request, db: AsyncSession = Depends(get_async_db)):
    try:
        current_user = request.state.user
        # Step 1: Get total comment count for the post
        current_user = request.state.user
        count_stmt = text("""
            SELECT COUNT(*) 
            FROM comments
            WHERE post_id = :post_id 
        """)
        count_result = await db.execute(count_stmt, {"post_id": post_id})
        total_count = count_result.scalar()

        # Step 2: Get all comments and replies
        result = await db.execute(_get_comments, {"post_id": post_id,"current_user_id":current_user.get('user_id')})
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
         
        return schemas.AllComment(
            comments=comments if comments else [],
            numb_found=total_count or 0
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    


@router.get('/comments/{comment_id}/replies', status_code=status.HTTP_200_OK, response_model = schemas.AllComment)
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
        result = await db.execute(_get_replies, {"comment_id": comment_id,"current_user_id":current_user.get('user_id')})
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
                 
        return schemas.AllComment(
            comments=comments if comments else [],
            numb_found=total_count or 0
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/comments/{comment_id}/comment', status_code=status.HTTP_200_OK)
async def get_comment(comment_id: str,request:Request, db: AsyncSession = Depends(get_async_db)):
    try:
        current_user = request.state.user
        result = await db.execute(_get_comment, {"comment_id": comment_id,"current_user_id":current_user.get('user_id')})
        row = result.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="No comment found.")

        return dict(row._mapping)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/comments/{comment_id}/like', status_code=status.HTTP_200_OK)
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
    
    

@router.post('/comments/{post_id}', status_code=status.HTTP_201_CREATED)
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



@router.post('/comments/{comment_id}/replies', status_code=status.HTTP_201_CREATED)
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
