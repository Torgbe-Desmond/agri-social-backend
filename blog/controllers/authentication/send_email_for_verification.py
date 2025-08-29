from fastapi import  HTTPException, Form, Depends, status 
from ... import schemas
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from blog.database import get_async_db
from ...utils import send_email_to_recipient,generate_random_string
from datetime import timedelta,datetime,timezone
from .route import authRoute

@authRoute.post("/send-verification-email", status_code=status.HTTP_200_OK, response_model=schemas.SuccessResponse)
async def send_email_for_verification(
    email: str = Form(...),
    db: AsyncSession = Depends(get_async_db)
):
    try:
        # Check if user exists
        result = await db.execute(
            text("SELECT * FROM users WHERE email = :email"),
            {"email": email}
        )
        user = result.fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="No such user")

        verification_string = generate_random_string()
        verification_expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

        # Save string and expiry
        await db.execute(
            text("""
                UPDATE users
                SET verification_string = :verification_string,
                    verification_expires_at = :expires_at
                WHERE id = :user_id
            """),
            {
                "verification_string": verification_string,
                "verification_expires_at": verification_expires_at,
                "user_id": user.id
            }
        )

        # Prepare verification email
        url = ["https://student-rep.vercel.app", "http://localhost:3000"]
        verification_data = {
            "username": user.username,
            "to": [user.email],
            "subject": "Agrisocial Email Verification",
            "verification_link": f"{url[1]}/{verification_string}/update-password/"
        }

        await send_email_to_recipient(verification_data)

        await db.commit()

        return schemas.SuccessResponse(
            success=True,
            message="Visit your email to verify password",
            data=None
        )

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))