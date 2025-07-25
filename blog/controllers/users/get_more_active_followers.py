from fastapi import Query, HTTPException, File, UploadFile, Depends
from ...import schemas
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from blog.database import get_async_db
from route import userRoute


@userRoute.get('/new-followers/{user_id}', response_model=schemas.AllFollowers)
async def get_more_active_followers(
    user_id: str,
    offset: int = Query(1, ge=1),
    limit: int = Query(3, gt=0),
    db: AsyncSession = Depends(get_async_db)
):
    try:
        get_followers_count_stmt = text("""
            SELECT COUNT(*) 
            FROM users 
            WHERE id != :user_id AND id NOT IN (
                SELECT following_id 
                FROM followers 
                WHERE follower_id = :user_id
            )
        """)
        total_count_result = await db.execute(get_followers_count_stmt, {"user_id": user_id})
        total_count = total_count_result.scalar()

        cal_offset = (offset - 1) * limit

        get_followers_stmt = text("""
            SELECT id, firstname, lastname, username, user_image 
            FROM users 
            WHERE id != :user_id AND id NOT IN (
                SELECT following_id 
                FROM followers 
                WHERE follower_id = :user_id
            )
            ORDER BY created_at DESC
            OFFSET :offset ROWS
            FETCH NEXT :limit ROWS ONLY
        """)

        result = await db.execute(get_followers_stmt, {
            "user_id": user_id,
            "offset": cal_offset,
            "limit": limit
        })
        followers = result.fetchall()

        return schemas.AllFollowers(followers=followers, numb_found=total_count)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



