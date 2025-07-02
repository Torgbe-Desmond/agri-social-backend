from fastapi import APIRouter, status, Query, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from blog.database import get_async_db
from .. import schemas
from ..utils.stored_procedure_strings import _get_notifications_by_user_id

router = APIRouter()

@router.get('/get-notifications/{user_id}', status_code=status.HTTP_200_OK, response_model=schemas.AllNotifications)
async def get_notifications(
    user_id: str,
    offset: int = Query(1, ge=1),
    limit: int = Query(10, gt=0),
    db: AsyncSession = Depends(get_async_db)
):
    try:
        # Get total count
        get_size_stmt = text("SELECT COUNT(*) FROM notifications WHERE user_id = :user_id")
        total_count_result = await db.execute(get_size_stmt, {"user_id": user_id})
        total_count = total_count_result.scalar()

        # Pagination offset
        cal_offset = (offset - 1) * limit

        # Use _get_notifications_by_user_id directly (it's already a TextClause)
        result = await db.execute(_get_notifications_by_user_id, {
            "user_id": user_id,
            "offset": cal_offset,
            "limit": limit
        })

        rows = result.fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail="No notifications found.")

        notifications = [dict(row._mapping) for row in rows]

        return schemas.AllNotifications(
            notifications=notifications,
            numb_found=total_count
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

