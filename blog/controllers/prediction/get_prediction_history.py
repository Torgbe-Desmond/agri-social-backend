from fastapi import HTTPException, Depends, status, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from pathlib import Path
from ... import schemas
from blog.database import  get_async_db
from .route import predictionRoute

@predictionRoute.get('/', response_model=schemas.AllPrediction, status_code=status.HTTP_200_OK)
async def get_prediction_history(request: Request, db: AsyncSession = Depends(get_async_db)):
    try:
        current_user = request.state.user

        count_stmt = text("SELECT COUNT(*) FROM predictions WHERE user_id = :user_id")
        result = await db.execute(count_stmt, {"user_id": str(current_user.get("user_id"))})
        total_count = result.scalar()

        stmt = text("""
            SELECT * FROM predictions 
            WHERE user_id = :user_id 
            ORDER BY created_at DESC
        """)
        result = await db.execute(stmt, {"user_id": str(current_user.get("user_id"))})
        predictions = result.fetchall()
        
        print(predictions)

        return schemas.AllPrediction(
            predictions=[row._mapping for row in predictions] if predictions else [],
            numb_found=total_count or 0
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
