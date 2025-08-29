from fastapi import HTTPException, Depends, status, Request,UploadFile,File
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from pathlib import Path
from ... import schemas
from blog.database import  get_async_db
from .route import predictionRoute
from ...utils.firebase_interactions import delete_file_from_storage

@predictionRoute.delete('/{prediction_id}')
async def delete_prediction(prediction_id: str, db: AsyncSession = Depends(get_async_db)):
    try:
        stmt = text("SELECT generated_name, user_id FROM predictions WHERE id = :prediction_id")
        result = await db.execute(stmt, {"prediction_id": prediction_id})
        row = result.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Prediction not found.")

        generated_name, user_id = row

        await db.execute(text("DELETE FROM predictions WHERE id = :prediction_id"), {"prediction_id": prediction_id})
        await delete_file_from_storage(user_id, generated_name)
        await db.commit()

        return {"prediction_id": prediction_id}

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
