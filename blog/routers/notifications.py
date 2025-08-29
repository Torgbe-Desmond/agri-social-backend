from fastapi import APIRouter, status, Query, Depends, HTTPException,Request, Form
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from blog.database import get_async_db
from .. import schemas
from ..utils.stored_procedure_strings import _get_notifications_by_user_id
from sqlalchemy import text, bindparam
from sqlalchemy.sql import tuple_

router = APIRouter()

@router.get('/notifications', status_code=status.HTTP_200_OK, response_model=schemas.AllNotifications)
async def get_notifications(
    request:Request,
    offset: int = Query(1, ge=1),
    limit: int = Query(10, gt=0),
    db: AsyncSession = Depends(get_async_db)
):
    try:
        # Get total count
        current_user = request.state.user
        get_size_stmt = text("SELECT COUNT(*) FROM notifications WHERE user_id = :user_id")
        total_count_result = await db.execute(get_size_stmt, {"user_id": str(current_user.get("user_id"))})
        total_count = total_count_result.scalar()

        # Pagination offset
        cal_offset = (offset - 1) * limit

        # Use _get_notifications_by_user_id directly (it's already a TextClause)
        result = await db.execute(_get_notifications_by_user_id, {
            "user_id": str(current_user.get("user_id")),
            "offset": cal_offset,
            "limit": limit
        })

        rows = result.fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail="No notifications found.")

        notifications = [dict(row._mapping) for row in rows]
        
        if notifications:    
            return schemas.AllNotifications(
                notifications=notifications,
                numb_found=total_count
            )
        
        return schemas.AllNotifications(notifications=[],numb_found=0) 

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.post('/notifications/read', status_code=status.HTTP_200_OK)
async def get_notifications(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    notification_id: List[str] = Form(...)
):
    try:
        current_user = request.state.user

        if not notification_id:
            raise HTTPException(status_code=400, detail="No notification IDs provided")

        # Use tuple_() to safely inject list into IN clause
        stmt = text("""
            UPDATE notifications
            SET is_read = :is_read
            WHERE id IN :ids AND user_id = :user_id
            RETURNING id
        """).bindparams(
            bindparam("ids", expanding=True)  # key to make :ids work with lists
        )

        result = await db.execute(
            stmt,
            {
                "ids": notification_id,
                "is_read": 1
            }
        )
        await db.commit()

        updated_ids = [row.id for row in result.fetchall()]
        return {"updated": updated_ids}

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))