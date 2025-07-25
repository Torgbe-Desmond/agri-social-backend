
from fastapi import  HTTPException, File, UploadFile, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from blog.database import get_async_db
from ...utils.firebase_interactions import upload_file_to_storage, delete_file_from_storage
from .route import userRoute

@userRoute.put("/update-profile-image/{user_id}")
async def update_user_profile(user_id: str, file: UploadFile = File(...), db: AsyncSession = Depends(get_async_db)):
    file_name = file.filename
    try:
        content_type = file.content_type
        file_bytes = await file.read()

        file_url = await upload_file_to_storage(user_id, file_name, file_bytes, content_type)
        if not file_url:
            raise HTTPException(status_code=500, detail="Failed to upload image")

        update_stmt = text("UPDATE users SET user_image = :user_image WHERE id = :user_id")
        await db.execute(update_stmt, {"user_image": file_url, "user_id": user_id})
        await db.commit()

        return "Upload was successful"

    except Exception as e:
        await delete_file_from_storage(user_id, file_name)
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))