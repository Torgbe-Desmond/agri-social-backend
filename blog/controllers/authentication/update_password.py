from fastapi import HTTPException, Form, Depends, status
from ... import schemas
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from blog.database import get_async_db
import uuid
import bcrypt
from datetime import timedelta,datetime,timezone
from .route import authRoute

@authRoute.put("/update-password", response_model=schemas.SuccessResponse)
async def update_password(
    verification_string: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_async_db),
):
    try:
        if not password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please enter password"
            )

        # Check user and expiry
        result = await db.execute(
            text("""
                SELECT id, verification_expires_at
                FROM users
                WHERE verification_string = :verification_string
            """),
            {"verification_string": verification_string}
        )
        user = result.fetchone()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid verification link"
            )

        # Check expiry
        if not user.verification_expires_at or datetime.now(timezone.utc) > user.verification_expires_at:
            raise HTTPException(status_code=400, detail="Verification link expired")

        hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        # Update password & clear verification string
        await db.execute(
            text("""
                UPDATE users
                SET password_hash = :password_hash,
                    verification_string = NULL,
                    verification_expires_at = NULL
                WHERE id = :user_id
            """),
            {"password_hash": hashed_password, "user_id": user.id}
        )

        await db.commit()

        return schemas.SuccessResponse(
            success=True,
            message="Password update was successful",
            data=None
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error occurred: {str(e)}"
        )