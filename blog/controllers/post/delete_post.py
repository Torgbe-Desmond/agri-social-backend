from fastapi import Query, Depends, HTTPException, status, Request, Form, UploadFile, File
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import uuid
from ... import schemas
from blog.database import get_async_db
from ...utils.firebase_interactions import delete_file_from_storage
from .route import postRoute

@postRoute.delete('/{post_id}')
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