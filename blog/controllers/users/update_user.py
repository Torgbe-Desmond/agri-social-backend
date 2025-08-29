from fastapi import  HTTPException, Form, Depends, status,Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from blog.database import get_async_db
from .route import userRoute
from typing import Optional
import uuid

@userRoute.put('/update')
async def update_user(
    request:Request,
    username: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    city: Optional[str] = Form(None),
    contact: Optional[str] = Form(None),
    firstname: Optional[str] = Form(None),
    lastname: Optional[str] = Form(None),
    interests: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_async_db),
):
    try:
        current_user = request.state.user         
        fields_to_update = []
        values = {"user_id": current_user.get("user_id")}
        if username:
            fields_to_update.append("username = :username")
            values["username"] = username
        if email:
            fields_to_update.append("email = :email")
            values["email"] = email
        if city:
            fields_to_update.append("city = :city")
            values["city"] = city
        if contact:
            fields_to_update.append("contact = :contact")
            values["contact"] = contact
        if firstname:
            fields_to_update.append("firstname = :firstname")
            values["firstname"] = firstname
        if lastname:
            fields_to_update.append("lastname = :lastname")
            values["lastname"] = lastname

        if fields_to_update:
            query = f"""
                UPDATE users
                SET {', '.join(fields_to_update)}
                WHERE id = :user_id
            """
            await db.execute(text(query), values)

        if interests:
            split_interests = [i.strip() for i in interests.split(",") if i.strip()]
            for interest in split_interests:
                check_stmt = text("""
                    SELECT 1 FROM user_interests 
                    WHERE user_id = :user_id AND interest = :interest
                """)
                result = await db.execute(check_stmt, {"user_id": current_user.get("user_id"), "interest": interest})
                if not result.fetchone():
                    interest_id = str(uuid.uuid4())
                    insert_stmt = text("""
                        INSERT INTO user_interests (id, user_id, interest, created_at)
                        VALUES (:id, :user_id, :interest, GETDATE())
                    """)
                    await db.execute(insert_stmt, {"id": interest_id, "user_id": current_user.get("user_id"), "interest": interest})

        await db.commit()
        return {"message": "User updated successfully."}

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

