from fastapi import  HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from blog.database import get_async_db
from ...utils.stored_procedure_strings import _get_user_profile
from .route import userRoute
from ...import schemas

@userRoute.get('/{user_id}', response_model=schemas.User)
async def get_all_users(user_id: str, db: AsyncSession = Depends(get_async_db)):
    result = await db.execute(_get_user_profile, {"userId": user_id})
    user = result.mappings().fetchone()
    print(user)

    if not user:
        raise HTTPException(status_code=404, detail="No users found")

    return user 