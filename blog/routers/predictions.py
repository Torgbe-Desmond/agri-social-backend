from fastapi import APIRouter, HTTPException, Depends, status, File, UploadFile, Form
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from typing import List, Optional
from pathlib import Path
import uuid
import tensorflow as tf
import os
from dotenv import load_dotenv

from .. import schemas
from ..utils import (
    predict_image_class,
    generate_random_string,
    download_and_process_file
)
from ..utils.firebase_interactions import (
    upload_file_to_storage,
    delete_file_from_storage
)
from blog.database import get_db, get_async_db

load_dotenv()

router = APIRouter()

# ------------------- GET PREDICTION HISTORY -------------------
@router.get('/prediction-history/{user_id}', response_model=List[schemas.Prediction], status_code=status.HTTP_200_OK)
async def get_prediction_history(user_id: str, db: AsyncSession = Depends(get_async_db)):
    try:
        stmt = text("""
            SELECT * FROM predictions 
            WHERE user_id = :user_id 
            ORDER BY created_at DESC
        """)
        result = await db.execute(stmt, {"user_id": user_id})
        predictions = result.mappings().all()
        
        print(predictions)

        if not predictions:
            raise HTTPException(status_code=404, detail="No prediction history found for this user.")

        return predictions

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


# ------------------- GET ONE PREDICTION -------------------
@router.get('/prediction/{user_id}/one/{prediction_id}', status_code=status.HTTP_200_OK)
def get_one_prediction_info(prediction_id: str, user_id: str, db: Session = Depends(get_db)):
    try:
        stmt = text("SELECT * FROM predictions WHERE id = :prediction_id AND user_id = :user_id")
        result = db.execute(stmt, {"prediction_id": prediction_id, "user_id": user_id}).fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="No prediction found")

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# # ------------------- CREATE PREDICTION -------------------
# @router.post('/prediction', status_code=status.HTTP_200_OK)
# async def create_prediction(user_id: str = Form(...), file: UploadFile = File(...), db: AsyncSession = Depends(get_async_db)):
#     try:
#         prediction_list = [
#             'Tomato Early Blight',
#             'Tomato Late Blight',
#             'Tomato Leaf Mold',
#             'Tomato Septoria Leaf Spot',
#             'Tomato Spider Mites Two Spotted Spider Mite',
#             'Tomato Target Spot',
#             'Tomato Yellow Leaf Curl Virus',
#             'Tomato Mosaic Virus',
#             'Tomato Healthy'
#         ]

#         model_path = Path(__file__).parent / "trained_tomato_disease_detection_model.h5"
#         model = tf.keras.models.load_model(model_path)

#         file_bytes = await file.read()
#         model_result = await predict_image_class(file_bytes, model)

#         if not model_result:
#             raise HTTPException(status_code=404, detail="Disease of image could not be predicted")

#         result_index, confidence = model_result
#         file_name = file.filename
#         extension = file_name.split(".")[-1]
#         generated_name = f"plant.disease.detection.{generate_random_string()}.{extension}"
#         content_type = file.content_type

#         if float(confidence) < 0.85:
#             return {
#                 "id": None,
#                 "user_id": user_id,
#                 "image_url": None,
#                 "confidence": confidence,
#                 "prediction_label": "Could not Predict Image",
#                 "filename": file_name,
#                 "generated_name": generated_name
#             }

#         result_index = max(0, result_index - 1)
#         image_url = await upload_file_to_storage(user_id, generated_name, file_bytes, content_type)

#         if not image_url:
#             raise HTTPException(status_code=404, detail="An error occurred while uploading the file.")

#         stmt = text("""
#             INSERT INTO predictions 
#             (user_id, image_url, created_at, confidence, prediction_label, filename, generated_name)
#             VALUES (:user_id, :image_url, NOW(), :confidence, :prediction_label, :filename, :generated_name)
#             RETURNING id
#         """)
#         result = await db.execute(stmt, {
#             "user_id": user_id,
#             "image_url": image_url,
#             "confidence": confidence,
#             "prediction_label": prediction_list[result_index],
#             "filename": file_name,
#             "generated_name": generated_name
#         })
        
#         created_prediction = result.fetchone()
#         prediction_id = created_prediction._mapping["id"]
        
#         await db.commit()

#         return {
#             "id": prediction_id,
#             "user_id": user_id,
#             "image_url": image_url,
#             "confidence": confidence,
#             "prediction_label": prediction_list[result_index],
#             "filename": file_name,
#             "generated_name": generated_name
#         }

#     except Exception as e:
#         await delete_file_from_storage(user_id,generated_name)
#         await db.rollback()
#         raise HTTPException(status_code=500, detail=str(e))


# ------------------- CREATE PREDICTION FROM POST IMAGE -------------------
# @router.post('/prediction-disease-image', status_code=status.HTTP_200_OK)
# async def create_prediction_from_post(post_id: Optional[str] = Form(None), comment_id: Optional[str] = Form(None), db: AsyncSession = Depends(get_async_db)):
#     try:
#         prediction_list = [
#             'Tomato Early Blight',
#             'Tomato Late Blight',
#             'Tomato Leaf Mold',
#             'Tomato Septoria Leaf Spot',
#             'Tomato Spider Mites Two Spotted Spider Mite',
#             'Tomato Target Spot',
#             'Tomato Yellow Leaf Curl Virus',
#             'Tomato Mosaic Virus',
#             'Tomato Healthy'
#         ]

#         if post_id:
#             stmt = text("SELECT image_url FROM post_images WHERE post_id = :post_id")
#             result = await db.execute(stmt, {"post_id": post_id})
#             post_image_url = result.fetchone()

#             if not post_image_url:
#                 raise HTTPException(status_code=404, detail="Image does not exist.")

#             file_bytes = download_and_process_file(post_image_url.image_url)

#             if not file_bytes:
#                 raise HTTPException(status_code=404, detail="Image file could not be downloaded.")

#             model_path = Path(__file__).parent / "trained_tomato_disease_detection_model.h5"
#             model = tf.keras.models.load_model(model_path)

#             model_result = await predict_image_class(file_bytes, model)
#             result_index, confidence = model_result

#             result_index = max(0, result_index - 1)
#             label = "Uncertain / Unknown" if confidence < 0.85 else prediction_list[result_index]

#             return {
#                 "post_id": post_id,
#                 "prediction_label": label,
#                 "confidence": confidence
#             }

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


# ------------------- DELETE PREDICTION -------------------
@router.delete('/delete-prediction/{prediction_id}')
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
