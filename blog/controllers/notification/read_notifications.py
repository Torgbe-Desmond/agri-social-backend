
from fastapi import APIRouter, status, Query, Depends, HTTPException,Request, Form
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from blog.database import get_async_db
from typing import List
from ... import schemas
from sqlalchemy import text,bindparam
from .route import notificationRoute

@notificationRoute.post("/read", status_code=200) 
async def get_notifications(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    notification_id: List[str] = Form(...)
):
    current_user = request.state.user

    if not notification_id:
        raise HTTPException(status_code=400, detail="No notification IDs provided")

    stmt = text("""
        UPDATE notifications
        SET is_read = :is_read
        WHERE id IN :ids AND user_id = :user_id
        RETURNING id
    """).bindparams(bindparam("ids", expanding=True))

    try:
        result = await db.execute(
            stmt,
            {
                "ids": notification_id,
                "user_id": current_user.get("user_id"),
                "is_read": 1
            }
        )
        await db.commit()
        updated_ids = [row[0] for row in result.fetchall()]
        return {"updated": updated_ids}

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
