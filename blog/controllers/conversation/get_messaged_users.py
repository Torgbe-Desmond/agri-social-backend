from fastapi import APIRouter, Depends, Request
from . import _schema
from sqlalchemy import text,bindparam
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from blog.database import get_async_db
router = APIRouter()
userMap = {}  
from .route import conversationRoute

@conversationRoute.get("/users", response_model=List[_schema.SharedConversationUser])
async def get_messaged_users(
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

        other_members AS (
            SELECT cm.conversation_id, u.id AS user_id, u.username, u.user_image, u.reference_id
            FROM conversation_members cm
            JOIN users u ON u.id = cm.user_id
            WHERE cm.conversation_id IN (SELECT conversation_id FROM user_conversations)
              AND cm.user_id != :current_user_id
        ),

        last_messages AS (
            SELECT DISTINCT ON (m.conversation_id)
                m.conversation_id,
                m.content AS last_message,
                m.created_at
            FROM messages m
            WHERE m.conversation_id IN (SELECT conversation_id FROM user_conversations)
            ORDER BY m.conversation_id, m.created_at DESC
        )

        SELECT
            om.conversation_id,
            om.user_id,
            om.username,
            om.user_image,
            om.reference_id,
            lm.last_message,
            lm.created_at
        FROM other_members om
        LEFT JOIN last_messages lm ON lm.conversation_id = om.conversation_id
        ORDER BY lm.created_at DESC NULLS LAST;
""")
, {"current_user_id":current_user.get("user_id")})
    users = result.mappings().all()  
    return users    