from fastapi import APIRouter, Depends, Request,Form,HTTPException
from . import _schema
from sqlalchemy import text,bindparam
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List,Optional
from blog.database import get_async_db
router = APIRouter()
userMap = {}  
from .route import conversationRoute

@conversationRoute.post("/groups/create", response_model=_schema.SharedConversationGroup)
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
        response_result = await db.execute(text("""
        WITH user_conversations AS (
        SELECT cm.conversation_id
        FROM conversation_members cm
        WHERE cm.user_id = :current_user_id
        ),
        
        group_conversations AS (
            SELECT c.id AS conversation_id, c.name AS group_name, c.created_at
            FROM conversations c
            WHERE c.is_group = 1 AND c.id IN (SELECT conversation_id FROM user_conversations)
        ),
        
        last_messages AS (
            SELECT DISTINCT ON (m.conversation_id)
                m.conversation_id,
                m.content AS last_message,
                m.created_at
            FROM messages m
            WHERE m.conversation_id IN (SELECT conversation_id FROM group_conversations)
            ORDER BY m.conversation_id, m.created_at DESC
        )
        
        SELECT 
            gc.conversation_id, 
            gc.group_name, 
            lm.last_message, 
            lm.created_at
        FROM group_conversations gc
        LEFT JOIN last_messages lm ON lm.conversation_id = gc.conversation_id
        ORDER BY lm.created_at DESC;
        """), {"current_user_id": current_user.get("user_id")})
        group_conversation = response_result.fetchone()
        if not group_conversation:
            raise HTTPException(status_code=404, detail="Group conversation not found")

        return group_conversation

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
