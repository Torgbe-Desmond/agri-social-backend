from fastapi import APIRouter, status, Query, Depends, HTTPException,Request, Form
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from blog.database import get_async_db
from ... import schemas
from sqlalchemy import text
from .route import notificationRoute

@notificationRoute.get('/notifications', response_model=schemas.AllNotifications)
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

        cal_offset = (offset - 1) * limit

        result = await db.execute(text("""
            SELECT 
                n.id,
                n.user_id,
                n.actor_id,
                n.type,
                n.entity_type,
                n.entity_id,
                n.action_id,
                n.message,
                COALESCE((SELECT user_image FROM users WHERE id = n.actor_id), '') AS user_image,
                COALESCE((SELECT username FROM users WHERE id = n.actor_id), '') AS username,
                COALESCE((
                       SELECT STRING_AGG(image_url, ',') 
                       FROM post_images 
                       WHERE post_id = n.entity_id::uuid
                   ), '') AS images,
                COALESCE((
                       SELECT STRING_AGG(video_url, ',') 
                       FROM post_videos 
                       WHERE post_id = n.entity_id::uuid
                   ), '') AS videos,        
                n.is_read,
                n.created_at
            FROM notifications n
            INNER JOIN users u ON n.user_id = u.id
            WHERE n.user_id = :user_id
            ORDER BY created_at DESC
            OFFSET :offset ROWS
            FETCH NEXT :limit ROWS ONLY
            """)
            , 
            {
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
