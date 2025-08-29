from fastapi import HTTPException,  Depends, status
from ... import schemas
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from blog.database import get_async_db
from ...middleware.authMiddleware import create_access_token
from datetime import timedelta
from .route import authRoute


@authRoute.get("/generate-verification-token/{verification_string}", response_model=schemas.SuccessResponse)
async def generate_token_for_verification(verification_string: str, db: AsyncSession = Depends(get_async_db)):
    try:
        if not verification_string:
             raise HTTPException(
                 status_code=status.HTTP_400_BAD_REQUEST,
                 detail="Reference ID is required"
             )
        
         # Fetch user details
        result = await db.execute(
             text("""
                 SELECT id, username, reference_id
                 FROM users
                 WHERE verification_string = :verification_string
             """),
             {"verification_string": verification_string}
         )
        user = result.fetchone()
    
        if not user:
            raise HTTPException(
                status_code=401,
                detail="Unauthorized"
            )
    
        # Create JWT token with 5 min expiry
        token = create_access_token(
            data={
                 "user_id": str(user.id),
                 "username": user.username,
                 "reference_id": str(user.reference_id)
             },
             expires_delta=timedelta(minutes=5)
         )
        
        return schemas.SuccessResponse(
             success=True,
             message="Token generated successfully",
             data={"verification_token": token}
         )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )