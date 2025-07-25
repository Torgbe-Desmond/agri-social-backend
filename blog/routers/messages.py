from fastapi import APIRouter, Query, HTTPException, File, UploadFile, Form, Depends, status, Request
from .. import schemas
from sqlalchemy import text,bindparam
from ..database.models import user_table, predictions_history_table
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from blog.database import get_async_db
from ..utils.firebase_interactions import upload_file_to_storage, delete_file_from_storage
from ..utils.stored_procedure_strings import _get_messaged_friends,_get_group_conversations
import uuid
import bcrypt
from uuid import UUID
router = APIRouter()
userMap = {}  # Stores user_id -> socket_id mapping



@router.post("/conversing")
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

        

@router.post("/get-messaged-users/", response_model=List[schemas.SharedConversationUser])
async def get_messaged_users(
    request:Request,
    db: AsyncSession = Depends(get_async_db),
):
    current_user = request.state.user
    result = await db.execute(_get_messaged_friends, {"current_user_id":current_user.get("user_id")})
    users = result.mappings().all()  
    return users    


@router.post("/get-group-conversations/", response_model=List[schemas.SharedConversationGroup])
async def get_group_conversations(
    request:Request,
    db: AsyncSession = Depends(get_async_db),
):  
    current_user = request.state.user
    print("current_user",current_user)
    result = await db.execute(_get_group_conversations, {"current_user_id": current_user.get("user_id")})
    users = result.mappings().all()  
    return users

@router.post("/create-group-conversation/", response_model=schemas.SharedConversationGroup)
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




@router.get("/get-messages/", response_model=List[schemas.MessageOut])
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
            (SELECT username FROM users WHERE id = s.sender_id) AS username,
            (SELECT user_image FROM users WHERE id = s.sender_id) AS user_image
            FROM messages s
            WHERE s.conversation_id = :conversation_id
            ORDER BY s.created_at ASC
        """)

        result = await db.execute(query, {"conversation_id": conversation_id})
        messages = result.mappings().all()  # returns list of dictionaries
        return [schemas.MessageOut(**row) for row in messages]
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch messages: {str(e)}")


@router.post('/messages/', response_model=schemas.MessageOut)
async def send_message(
    request:Request,
    content: str = Form(...),
    member_ids: List[str] = Form(...),
    name: Optional[str] = Form(None),
    is_group: Optional[int] = Form(None),
    conversation_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_async_db)
):
    try:
        from ..socket_manager import sio,getSocket
        new_conversation_id = conversation_id
        edited_member_ids =  member_ids[0].split(",")
        # Step 1: Create a new conversation if not provided
        current_user = request.state.user
        if not conversation_id:
            columns = []
            placeholders = []
            values = {}

            if name:
                columns.append("name")
                placeholders.append(":name")
                values["name"] = name

            if is_group is not None:
                columns.append("is_group")
                placeholders.append(":is_group")
                values["is_group"] = is_group

            columns.append("created_at")
            placeholders.append("NOW()")

            query = f"""
                INSERT INTO conversations ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
                RETURNING id
            """

            result = await db.execute(text(query), values)
            conversation = result.fetchone()

            if not conversation:
                raise HTTPException(status_code=500, detail="Failed to create conversation")

            new_conversation_id = conversation.id

            # Step 2: Insert members into conversation_members
            insert_member_query = text("""
                INSERT INTO conversation_members (conversation_id, user_id)
                VALUES (:conversation_id, :user_id)
            """)
            for uid in edited_member_ids:
                await db.execute(insert_member_query, {
                    "conversation_id": str(new_conversation_id),
                    "user_id": uid
                })

        # Step 3: Insert the message
        insert_msg_query = text("""
            INSERT INTO messages (conversation_id, sender_id, content, created_at)
            VALUES (:conversation_id, :sender_id, :content, NOW())
            RETURNING id, conversation_id, sender_id, content, created_at
        """)
        result = await db.execute(insert_msg_query, {
            "conversation_id": str(new_conversation_id),
            "sender_id": current_user.get("user_id"),
            "content": content
        })

        row = result.fetchone()
        
        get_user_info_query = await db.execute(text("""
            SELECT user_image 
            FROM users
            WHERE id =:user_id
        """),{
            "user_id":current_user.get("user_id")
        })
        
        user_image = get_user_info_query.fetchone()
    
        await db.commit()
        
        # query = text("""
        #     SELECT id, conversation_id, sender_id, content, created_at
        #     FROM messages
        #     WHERE conversation_id = :conversation_id
        #     ORDER BY created_at ASC
        # """)
        
        # result_ = await db.execute(query, {"conversation_id": str(row.conversation_id)})
        # messages = result_.fetchall()
        # print(messages)

        if not row:
            raise HTTPException(status_code=500, detail="Failed to send message")

        # Step 4: Emit real-time message if it's a direct chat
        if not is_group:
            receiver_ids = [uid for uid in edited_member_ids if uid != current_user.get("reference_id")]
            if receiver_ids:
                receiver_id = receiver_ids[0]
                sid = getSocket(receiver_id)

                if sid:
                   await sio.emit("chat_response", {
                        "id": str(row.id),
                        "conversation_id": str(row.conversation_id),
                        "sender_id": str(row.sender_id),
                        "content": row.content,
                        "created_at": row.created_at.isoformat(),
                        "user_image":user_image
                    }, to=str(sid))
        # Step 5: Return message using Pydantic schema
        return schemas.MessageOut(
            id=str(row.id),
            conversation_id=str(row.conversation_id),
            sender_id=str(row.sender_id),
            content=row.content,
            created_at=row.created_at
        )

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@router.post('/create-conversation', status_code=status.HTTP_201_CREATED)
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