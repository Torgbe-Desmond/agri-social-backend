from fastapi import APIRouter, Depends, Request,Form,UploadFile,HTTPException,status
from sqlalchemy import text,bindparam
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from blog.database import get_async_db
router = APIRouter()
userMap = {}  
from .route import conversationRoute

@conversationRoute.post('/create', status_code=status.HTTP_201_CREATED)
async def create_conversation(
    request: Request,
    member_ids: List[str] = Form(...),
    db: AsyncSession = Depends(get_async_db)
):
    try:
        query = """
            INSERT INTO conversations (created_at)
            VALUES (NOW())
            RETURNING id
        """
        result = await db.execute(text(query))
        conversation = result.fetchone()
        if not conversation:
            raise HTTPException(status_code=500, detail="Failed to create conversation")

        new_conversation_id = conversation[0]  
        
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