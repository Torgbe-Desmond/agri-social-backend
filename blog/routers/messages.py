from fastapi import APIRouter, Query, HTTPException, File, UploadFile, Form, Depends, status, Request
from .. import schemas
from sqlalchemy import text,bindparam
from ..database.models import user_table, predictions_history_table
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from blog.database import get_async_db
from ..utils.stored_procedure_strings import _get_messaged_friends,_get_group_conversations
import uuid
import bcrypt
from ..utils import generate_random_string
from uuid import UUID
router = APIRouter()
userMap = {}  # Stores user_id -> socket_id mapping
from ..utils.firebase_interactions import upload_file_to_storage, delete_file_from_storage



@router.post("/conversation/conversing")
async def get_messaged_users(
    request: Request,
    member_ids: List[str] = Form(...),
    db: AsyncSession = Depends(get_async_db),
):
    try:
        query = text("""
            SELECT cm.conversation_id
            FROM conversation_members cm
            JOIN conversations c ON cm.conversation_id = c.id
            WHERE cm.user_id IN :user_ids
              AND c.is_group IS NULL
            GROUP BY cm.conversation_id
            HAVING COUNT(DISTINCT cm.user_id) = :user_count
        """).bindparams(
            bindparam("user_ids", expanding=True),
            bindparam("user_count")
        )

        result = await db.execute(query, {
            "user_ids": member_ids,
            "user_count": 2
        })
        
        row = result.fetchone()

        if row:
            conversation_id = row.conversation_id
            print(conversation_id)
            return {"conversation_id": conversation_id}
        
        # If no conversation found
        return {"conversation_id": None}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

        

@router.get("/conversation/users", response_model=List[schemas.SharedConversationUser])
async def get_messaged_users(
    request:Request,
    db: AsyncSession = Depends(get_async_db),
):
    current_user = request.state.user
    result = await db.execute(_get_messaged_friends, {"current_user_id":current_user.get("user_id")})
    users = result.mappings().all()  
    return users    


@router.post("/conversation/group", response_model=List[schemas.SharedConversationGroup])
async def get_group_conversations(
    request:Request,
    db: AsyncSession = Depends(get_async_db),
):  
    current_user = request.state.user
    print("current_user",current_user)
    result = await db.execute(_get_group_conversations, {"current_user_id": current_user.get("user_id")})
    users = result.mappings().all()  
    return users

@router.post("/conversation/groups/create", response_model=schemas.SharedConversationGroup)
async def create_group_conversation(
    request:Request,
    sender_id: str = Form(...),
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    is_group: Optional[int] = Form(None),
    db: AsyncSession = Depends(get_async_db)
):
    try:
        current_user = request.state.user
        if not name or is_group is None:
            raise HTTPException(status_code=400, detail="Please enter all required fields")

        # Step 1: Insert into conversations
        insert_convo_query = text("""
            INSERT INTO conversations (name, owner, is_group,description, created_at)
            VALUES (:name, :owner, :is_group,:description, NOW())
            RETURNING id
        """)
        result = await db.execute(insert_convo_query, {
            "name": name,
            "owner": current_user.get("user_id"),
            "description":description,
            "is_group": is_group
        })
        convo_row = result.fetchone()
        if not convo_row:
            raise HTTPException(status_code=500, detail="Failed to create conversation")
        
        conversation_id = convo_row.id

        # Step 2: Add creator to conversation_members
        await db.execute(text("""
            INSERT INTO conversation_members (conversation_id, user_id)
            VALUES (:conversation_id, :user_id)
        """), {
            "conversation_id": conversation_id,
            "user_id": current_user.get("user_id")
        })

        await db.commit()

        # Step 3: Fetch and return the created group conversation
        response_result = await db.execute(_get_group_conversations, {"current_user_id": current_user.get("user_id")})
        group_conversation = response_result.fetchone()
        if not group_conversation:
            raise HTTPException(status_code=404, detail="Group conversation not found")

        return group_conversation

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@router.post("/join-group-conversation/", response_model=schemas.SharedConversationGroup)
async def join_group_conversation(
    request:Request,
    conversation_id:str = Form(...),
    db: AsyncSession = Depends(get_async_db)
):
    try:
        current_user = request.state.user
        result = await db.execute(text("""
            SELECT conversation_id,user_id
            FROM conversation_members 
            WHERE user_id =:user_id AND conversation_id =:conversation_id
        """,{
            "conversation_id": conversation_id,
            "user_id": current_user.get("user_id") 
        }))
        
        user = result.first()
        
        if user:
            raise HTTPException(status_code=500, detail="You have already joined this group")
        
        await db.execute(text("""
            INSERT INTO conversation_members (conversation_id, user_id)
            VALUES (:conversation_id, :user_id)
        """), {
            "conversation_id": conversation_id,
            "user_id": current_user.get("user_id")
        })

        await db.commit()

        return {"message":"group was joined successfully"}

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@router.get("/conversation/{conversation_id}/messages", response_model=List[schemas.MessageOut])
async def get_messages(
    conversation_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    try:
        query = text("""
           SELECT 
            s.id, 
            s.conversation_id, 
            s.sender_id, 
            s.content, 
            s.created_at,

            COALESCE((
                SELECT STRING_AGG(image_url, ',') 
                FROM message_images 
                WHERE message_id = s.id
            ), '') AS images,

            COALESCE((
                SELECT STRING_AGG(video_url, ',') 
                FROM message_videos 
                WHERE message_id = s.id
            ), '') AS videos,

            (SELECT username FROM users WHERE id = s.sender_id) AS username,
            (SELECT user_image FROM users WHERE id = s.sender_id) AS user_image

        FROM messages s
        WHERE s.conversation_id = :conversation_id
        GROUP by s.id,s.conversation_id,s.sender_id, s.content, s.created_at
        ORDER BY s.created_at ASC
        """)

        result = await db.execute(query, {"conversation_id": conversation_id})
        messages = result.mappings().all()  # returns list of dictionaries
        return [schemas.MessageOut(**row) for row in messages]
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch messages: {str(e)}")

@router.post('/conversation/send', response_model=schemas.MessageOut)
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
        from ..socket_manager import sio, getSocket
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

        return schemas.MessageOut(
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

@router.post('/conversation/create', status_code=status.HTTP_201_CREATED)
async def create_conversation(
    request: Request,
    member_ids: List[str] = Form(...),
    db: AsyncSession = Depends(get_async_db)
):
    try:
        # Step 1: Create new conversation
        query = """
            INSERT INTO conversations (created_at)
            VALUES (NOW())
            RETURNING id
        """
        result = await db.execute(text(query))
        conversation = result.fetchone()
        if not conversation:
            raise HTTPException(status_code=500, detail="Failed to create conversation")

        new_conversation_id = conversation[0]  # or conversation.id depending on DB return format
        
        # Step 2: Insert members into conversation_members
        insert_member_query = text("""
            INSERT INTO conversation_members (conversation_id, user_id)
            VALUES (:conversation_id, :user_id)
        """)
        for uid in member_ids:
            await db.execute(insert_member_query, {
                "conversation_id": new_conversation_id,
                "user_id": uid
            })

        await db.commit()

        return {
            "message": "Conversation created successfully",
            "conversation_id": new_conversation_id
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")