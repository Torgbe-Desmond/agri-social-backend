from fastapi import APIRouter, UploadFile, File, Form, Query, Depends, HTTPException, status, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import uuid
from .. import schemas
from blog.database import get_async_db
from ..utils.firebase_interactions import upload_file_to_storage, delete_file_from_storage
from ..utils import generate_random_string
from ..utils.stored_procedure_strings import _get_recommeneded_post, _get_post, _get_post_history,_get_all_posts,_get_single_post,_get_all_streams

router = APIRouter()

@router.get('/get-single-post/{post_id}', response_model=schemas.GetAllPost)
async def get_single_post(post_id: str, db: AsyncSession = Depends(get_async_db)):
    try:
        result = await db.execute(_get_single_post, {"currentPostId": post_id})
        post = result.fetchone()

        if not post:
            raise HTTPException(status_code=404, detail="No recommended posts found.")

        return post._mapping

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/get-streams', response_model=schemas.AllPost)
async def get_streams(
    request:Request,
    offset: int = Query(1, ge=0),
    limit: int = Query(3, gt=0),
    db: AsyncSession = Depends(get_async_db)
):
    try:
        current_user = request.state.user
        count_stmt = text("SELECT COUNT(*) FROM posts")
        result = await db.execute(count_stmt)
        total_count = result.scalar()
        cal_offset = (offset - 1) * limit
        result = await db.execute(_get_all_streams, {"offset": cal_offset, "limit": limit})
        posts = [dict(row._mapping) for row in result.fetchall()]
        
        return schemas.AllPost(posts=posts, numb_found=total_count)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/get-posts', response_model=schemas.AllPost)
async def get_post(
    request:Request,
    offset: int = Query(1, ge=0),
    limit: int = Query(10, gt=0),
    db: AsyncSession = Depends(get_async_db)
):
    try:
        current_user = request.state.user
        count_stmt = text("SELECT COUNT(*) FROM posts")
        result = await db.execute(count_stmt)
        total_count = result.scalar()
        cal_offset = (offset - 1) * limit
        result = await db.execute(_get_all_posts, {"offset": cal_offset, "limit": limit})
    
        if result:
            posts = [dict(row._mapping) for row in result.fetchall()]
            return schemas.AllPost(posts=posts, numb_found=total_count)
        
        return schemas.AllPost(posts=[], numb_found=0)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post('/create-post', status_code=status.HTTP_201_CREATED, response_model=schemas.GetAllPost)
async def create_post(
    request:Request,
    content: str = Form(...),
    image_url: Optional[str] = Form(None),
    has_video: Optional[int] = Form(None),
    tags: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_async_db)
):
    file_name = None
    generated_name = None
    try:
        
        current_user = request.state.user
        video_value = 0  
        if(has_video):
            video_value = has_video
            
        post_result = await db.execute(text("""
        INSERT INTO posts (user_id, content, has_video)
        VALUES (:user_id, :content, :has_video)
        RETURNING id
        """), {"user_id": current_user.get("user_id"), "content": content, "has_video":video_value})

        create_post = post_result.fetchone()
        post_id = create_post._mapping["id"]
        
        if tags:
            tag_list = tags.split(",")
            for tag in tag_list:
                await db.execute(text("""
                    INSERT INTO tags ( tag_name, created_at, post_id, creator)
                    VALUES( :tag_name, NOW(), :post_id, :creator)
                """), {
                    "tag_name": tag,
                    "post_id": post_id,
                    "creator": "user"
                })

        if image_url:
            generated_name = generate_random_string()
            await db.execute(text("""
                INSERT INTO post_images ( post_id, image_url, filename, user_id, generated_name)
                VALUES ( :post_id, :image_url, :filename , :user_id, :generated_name)
            """), {"post_id": post_id, "image_url": image_url, "filename": file_name, "user_id": current_user.get("user_id"), "generated_name": generated_name})

        if file:
            mimetype = file.content_type.split("/")[0]
            content_type = file.content_type
            file_bytes = await file.read()
            file_name = file.filename
            extension = file_name.split(".")[-1]
            generated_name = f"plant.disease.detection.{generate_random_string()}.{extension}"

            file_url = await upload_file_to_storage(current_user.get("user_id"), generated_name, file_bytes, content_type)

            if file_url:

                if mimetype == "image":
                    await db.execute(text("""
                        INSERT INTO post_images (post_id, image_url, filename, user_id, generated_name)
                        VALUES ( :post_id, :image_url, :filename , :user_id, :generated_name)
                    """), {"post_id": post_id, "image_url": file_url, "filename": file_name, "user_id": current_user.get("user_id"), "generated_name": generated_name})

                elif mimetype == "video":
                    await db.execute(text("""
                        INSERT INTO post_videos ( post_id, video_url, filename, user_id, generated_name)
                        VALUES ( :post_id, :video_url, :filename, :user_id, :generated_name)
                    """), {"post_id": post_id, "video_url": file_url, "filename": file_name, "user_id": current_user.get("user_id"), "generated_name": generated_name})

        await db.commit()

        result = await db.execute(_get_single_post, {"currentPostId": str(post_id)})
        created_post = result.fetchone()
        # return created_post._mapping
 
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
        if file and file_name:
            await delete_file_from_storage(current_user.get("user_id"), file_name)
        raise HTTPException(status_code=500, detail=str(e))

@router.delete('/delete-post/{post_id}')
async def delete_post(post_id: str, db: AsyncSession = Depends(get_async_db)):
    try:
        list_of_files_to_delete = []

        image_stmt = text("SELECT filename, user_id FROM post_images WHERE post_id=:post_id")
        image_result = await db.execute(image_stmt, {"post_id": post_id})
        image_row = image_result.fetchone()

        if image_row:
            list_of_files_to_delete.append({"filename": image_row.filename, "user_id": image_row.user_id})
            await db.execute(text("DELETE FROM post_images WHERE post_id=:post_id"), {"post_id": post_id})

        video_stmt = text("SELECT filename, user_id FROM post_videos WHERE post_id=:post_id")
        video_result = await db.execute(video_stmt, {"post_id": post_id})
        video_row = video_result.fetchone()

        if video_row:
            list_of_files_to_delete.append({"filename": video_row.filename, "user_id": video_row.user_id})
            await db.execute(text("DELETE FROM post_videos WHERE post_id=:post_id"), {"post_id": post_id})

        await db.execute(text("DELETE FROM posts WHERE id=:post_id"), {"post_id": post_id})

        for file_data in list_of_files_to_delete:
            await delete_file_from_storage(file_data["user_id"], file_data["filename"])

        await db.commit()
        return {"message": "Post deleted successfully", "post_id": post_id}

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/post-history", response_model=schemas.AllPost)
async def post_history(
    request: Request, 
    offset: int = Query(1, ge=1),         # Start from page 1
    limit: int = Query(10, gt=0),         # Must request at least 1 item
    db: AsyncSession = Depends(get_async_db)):
    try:
        current_user = request.state.user
        user_id = current_user.get("user_id")
        
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
        result = await db.execute(_get_post_history, {"user_id": user_id, "offset": cal_offset,
            "limit": limit})
        posts = result.fetchall()

        return schemas.AllPost(
            posts=[row._mapping for row in posts] if posts else [],
            numb_found=total_count or 0
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching post history: {str(e)}")


@router.get('/user-post-history/{user_id}', response_model=schemas.AllPost)
async def post_history(
    user_id, 
    offset: int = Query(1, ge=1),         # Start from page 1
    limit: int = Query(10, gt=0),         # Must request at least 1 item
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
        result = await db.execute(_get_post_history, {"user_id": user_id, "offset": cal_offset,
            "limit": limit})
        posts = result.fetchall()

        return schemas.AllPost(
            posts=[row._mapping for row in posts] if posts else [],
            numb_found=total_count or 0
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching post history: {str(e)}")
