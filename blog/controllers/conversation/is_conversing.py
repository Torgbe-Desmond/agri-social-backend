from fastapi import APIRouter, Query, HTTPException, File, UploadFile, Form, Depends, status, Request
from sqlalchemy import text,bindparam
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from blog.database import get_async_db
import uuid
import bcrypt
from ...utils import generate_random_string
from uuid import UUID
router = APIRouter()
userMap = {}  
from .route import conversationRoute

@conversationRoute.post("/conversing")
async def is_conversing(
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
