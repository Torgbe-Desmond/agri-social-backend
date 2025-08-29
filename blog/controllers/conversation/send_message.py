from fastapi import APIRouter, Depends, Request,Form,UploadFile,HTTPException,File
from . import _schema
from sqlalchemy import text,bindparam
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List,Optional
from blog.database import get_async_db
from ...utils import generate_random_string
from ...utils.firebase_interactions import upload_file_to_storage,delete_file_from_storage
router = APIRouter()
userMap = {}  
from .route import conversationRoute

@conversationRoute.post('/send', response_model=_schema.MessageOut)
async def send_message(
    request: Request,
    content: str = Form(...),
    member_ids: List[str] = Form(...),
    name: Optional[str] = Form(None),
    is_group: Optional[int] = Form(None),
    files: Optional[List[UploadFile]] = File(None),
    conversation_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_async_db)
):
    try:
        from ...socket_manager import sio, getSocket
        current_user = request.state.user
        edited_member_ids = member_ids[0].split(",")
        new_conversation_id = conversation_id

        image_urls = []
        video_urls = []
        generated_names = []

        # 1. Insert the base message
        msg_result = await db.execute(text("""
            INSERT INTO messages (conversation_id, sender_id, content, created_at)
            VALUES (:conversation_id, :sender_id, :content, NOW())
            RETURNING id, conversation_id, sender_id, content, created_at
        """), {
            "conversation_id": str(new_conversation_id),
            "sender_id": current_user.get("user_id"),
            "content": content
        })
        row = msg_result.fetchone()
        if not row:
            await db.rollback()
            raise HTTPException(status_code=500, detail="Failed to create message")
        row = row._mapping

        # 2. Process file uploads and insert into your tracking tables
        if files:
            for file in files:
                mimetype = file.content_type.split("/")[0]
                content_type = file.content_type
                file_bytes = await file.read()
                extension = file.filename.split(".")[-1]
                generated_name = f"plant.disease.detection.{generate_random_string()}.{extension}"
                generated_names.append(generated_name)

                file_url = await upload_file_to_storage(current_user.get("user_id"), generated_name, file_bytes, content_type)

                if file_url:
                    if mimetype == "image":
                        image_urls.append(file_url)
                        await db.execute(text("""
                            INSERT INTO message_images 
                            (message_id, image_url, filename, user_id, generated_name)
                            VALUES (:msg_id, :url, :fname, :uid, :gname)
                        """), {
                            "msg_id": row["id"],
                            "url": file_url,
                            "fname": file.filename,
                            "uid": current_user.get("user_id"),
                            "gname": generated_name
                        })
                    elif mimetype == "video":
                        video_urls.append(file_url)
                        await db.execute(text("""
                            INSERT INTO message_videos 
                            (message_id, video_url, filename, user_id, generated_name)
                            VALUES (:msg_id, :url, :fname, :uid, :gname)
                        """), {
                            "msg_id": row["id"],
                            "url": file_url,
                            "fname": file.filename,
                            "uid": current_user.get("user_id"),
                            "gname": generated_name
                        })

        # 3. Fetch sender image
        user_info = await db.execute(text("SELECT user_image FROM users WHERE id = :uid"), {
            "uid": current_user.get("user_id")
        })
        img_row = user_info.fetchone()
        user_image = img_row.user_image if img_row else None

        await db.commit()

        # 4. Emit via WebSocket to other member(s)
        receiver_ids = [uid for uid in edited_member_ids if uid != current_user.get("reference_id")]
        if receiver_ids:
            sid = getSocket(receiver_ids[0])
            if sid:
                await sio.emit("chat_response", {
                    "id": str(row["id"]),
                    "conversation_id": str(row["conversation_id"]),
                    "sender_id": str(row["sender_id"]),
                    "content": row["content"],
                    "created_at": row["created_at"].isoformat(),
                    "image_urls": image_urls,
                    "video_urls": video_urls,
                    "user_image": user_image
                }, to=str(sid))

        return _schema.MessageOut(
            id=str(row["id"]),
            conversation_id=str(row["conversation_id"]),
            sender_id=str(row["sender_id"]),
            content=row["content"],
            image_url=",".join(image_urls) if image_urls else None,
            video_url=",".join(video_urls) if video_urls else None,
            created_at=row["created_at"]
        )

    except Exception as e:
        await db.rollback()
        if generated_names:
            for gen_name in generated_names:
                try:
                    await delete_file_from_storage(current_user.get("user_id"), gen_name)
                except Exception as cleanup_error:
                    print(f"Failed to delete uploaded file {gen_name}: {cleanup_error}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
