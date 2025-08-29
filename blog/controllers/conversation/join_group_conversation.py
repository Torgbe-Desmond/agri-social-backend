from fastapi import APIRouter, Depends, Request,Form,HTTPException
from . import _schema
from sqlalchemy import text,bindparam
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List,Optional
from blog.database import get_async_db
router = APIRouter()
userMap = {}  
from .route import conversationRoute

@conversationRoute.post("/join-group", response_model=_schema.SharedConversationGroup)
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
