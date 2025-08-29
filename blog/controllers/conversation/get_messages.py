from fastapi import APIRouter, Query, HTTPException, File, UploadFile, Form, Depends, status, Request
from . import _schema
from sqlalchemy import text,bindparam
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from blog.database import get_async_db
import uuid
import bcrypt
from uuid import UUID
router = APIRouter()
userMap = {}  
from .route import conversationRoute

@conversationRoute.get("/{conversation_id}/messages", response_model=List[_schema.MessageOut])
async def get_messages(
    conversation_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    try:
        result = await db.execute(text("""
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
        """), {"conversation_id": conversation_id})
        messages = result.mappings().all()  
        return [_schema.MessageOut(**row) for row in messages]
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch messages: {str(e)}")