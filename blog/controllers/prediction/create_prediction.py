from fastapi import HTTPException, Depends, status, Request,UploadFile,File
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from pathlib import Path
from ... import schemas
from blog.database import  get_async_db
from .route import predictionRoute
from ...utils import  _predict_image_class,TomatoDiseaseCNN,generate_random_string
import torchvision.transforms as transforms
import torch
from ...utils.firebase_interactions import upload_file_to_storage,delete_file_from_storage

@predictionRoute.post('/prediction', status_code=status.HTTP_200_OK, response_model=schemas.Prediction)
async def create_prediction(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db)
):
    current_user = request.state.user
    generated_name = None
    
    PREDICTION_LIST =[
        "Apple_scab",
        "Apple_black_rot",
        "Apple_cedar_apple_rust",
        "Apple_healthy",
        "Background_without_leaves",
        "Blueberry_healthy",
        "Cherry-powdery_mildew",
        "Cherry_healthy",
        "Corn_gray_leaf_spot",
        "Corn_common_rust",
        "Corn_northern_leaf_blight",
        "Corn_healthy",
        "Grape_black_rot",
        "Grape_black_measles",
        "Grape_leaf_blight",
        "Grape_healthy",
        "Orange_haunglongbing",
        "Peach_bacterial_spot",
        "Peach_healthy",
        "Pepper_bacterial_spot",
        "Pepper_healthy",
        "Potato_early_blight",
        "Potato_healthy",
        "Potato_late_blight",
        "Raspberry_healthy",
        "Soybean_healthy",
        "Soybean_healthy",
        "Squash_powdery_mildew",
        "Strawberry_healthy",
        "Strawberry_leaf_scorch",
        "Tomato_bacterial_spot",
        "Tomato_early_blight",
        "Tomato_healthy",
        "Tomato_late_blight",
        "Tomato_leaf_mold",
        "Tomato_septoria_leaf_spot",
        "Tomato_spider_mites_two-spotted_spider_mite",
        "Tomato_target_spot",
        "Tomato_mosaic_virus",
        "Tomato_yellow_leaf_curl_virus"
    ]
    
    # Load model once at startup
    MODEL_PATH = Path(__file__).parent / "../ml_models/plant_disease_model_1_latest.pt"
    
    # Initialize model
    model = TomatoDiseaseCNN(num_classes=9)

    # Load checkpoint ignoring missing/unexpected keys
    checkpoint = torch.load(MODEL_PATH, map_location='cpu')
    model.load_state_dict(checkpoint, strict=False)

    # Set model to evaluation mode
    model.eval()

    # Image preprocessing
    transform = transforms.Compose([
        transforms.Resize((256, 256)),
        transforms.ToTensor(),
    ])

    try:
        file_bytes = await file.read()
        result_index, confidence = await _predict_image_class(file_bytes, model)

        file_name = file.filename
        extension = file_name.split(".")[-1]
        generated_name = f"plant.disease.detection.{generate_random_string()}.{extension}"
        content_type = file.content_type
        
        
        print(confidence)

        if float(confidence) < 0.85:
            return {
                "id": None,
                "user_id": current_user.get("user_id"),
                "image_url": None,
                "confidence": confidence,
                "prediction_label": "Could not Predict Image",
                "filename": file_name,
                "generated_name": generated_name
            }

        image_url = await upload_file_to_storage(
            current_user.get("user_id"), generated_name, file_bytes, content_type
        )
        if not image_url:
            raise HTTPException(status_code=404, detail="An error occurred while uploading the file.")

        stmt = text("""
            INSERT INTO predictions 
            (user_id, image_url, created_at, confidence, prediction_label, filename, generated_name)
            VALUES (:user_id, :image_url, NOW(), :confidence, :prediction_label, :filename, :generated_name)
            RETURNING id, created_at
        """)
        result = await db.execute(stmt, {
            "user_id": current_user.get("user_id"),
            "image_url": image_url,
            "confidence": confidence,
            "prediction_label": PREDICTION_LIST[result_index],
            "filename": file_name,
            "generated_name": generated_name
        })

        created_prediction = result.fetchone()
        await db.commit()

        return schemas.Prediction(
            id=created_prediction._mapping["id"],
            user_id=current_user.get("user_id"),
            image_url=image_url,
            confidence=confidence,
            prediction_label=PREDICTION_LIST[result_index],
            generated_name=generated_name,
            created_at=created_prediction._mapping["created_at"]
        )

    except Exception as e:
        if generated_name:
            await delete_file_from_storage(current_user.get("user_id"), generated_name)
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
