from fastapi import APIRouter, Depends, Request
from . import _schema
from sqlalchemy import text,bindparam
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from blog.database import get_async_db
router = APIRouter()
userMap = {}  
from .route import conversationRoute

@conversationRoute.post("/group", response_model=List[_schema.SharedConversationGroup])
async def get_group_conversations(
    request:Request,
    db: AsyncSession = Depends(get_async_db),
):  
    current_user = request.state.user
    result = await db.execute(text("""
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
    users = result.mappings().all()  
    return users