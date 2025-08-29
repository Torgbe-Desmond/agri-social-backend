from fastapi import  status, Depends, HTTPException,Query,Form,Request,File,UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from ... import schemas
from typing import Optional, List
from blog.database import get_async_db
from .route import productRoute
from ...utils import generate_random_string
from ...utils.firebase_interactions import upload_file_to_storage,delete_file_from_storage


@productRoute.post('/', status_code=status.HTTP_200_OK, response_model=schemas.Products)
async def create_product(
    request:Request,
    title: str = Form(...),
    description: Optional[str] = Form(None),
    price: str = Form(...),
    oldPrice: Optional[str] = Form(None),
    unit: Optional[str] = Form(None),
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_async_db)
):
    uploaded_files = []  
    try:
        current_user = request.state.user
        result = await db.execute(text("""
            INSERT INTO products (
                title, description, price, unit, user_id
            ) VALUES (
                :title, :description, :price, :unit, :user_id
            ) RETURNING id
        """), {
            "title": title,
            "description": description,
            "price": price,
            "unit": unit,
            "user_id": current_user.get("user_id")
        })
        product_id = result.scalar_one()

        for file in files:
            content_type = file.content_type
            file_bytes = await file.read()
            file_name = file.filename
            extension = file_name.split('.')[-1]
            generated_name = f"plant.disease.detection.{generate_random_string()}.{extension}"

            file_url = await upload_file_to_storage(current_user.get("user_id"), generated_name, file_bytes, content_type)
            if not file_url:
                raise HTTPException(status_code=500, detail="Error uploading file")

            uploaded_files.append(generated_name)

            await db.execute(text("""
                INSERT INTO product_images (
                    product_id, image_url, user_id, filename, generated_name
                ) VALUES (
                    :product_id, :image_url, :user_id, :filename, :generated_name
                )
            """), {
                "product_id": product_id,
                "image_url": file_url,
                "user_id": current_user.get("user_id"),
                "filename": file_name,
                "generated_name": generated_name
            })

        result = await db.execute(text("""
            SELECT 
                p.id AS product_id,
                p.title,
                p.description,
                p.price,
                p.unit,
                p.user_id,
                p.created_at,
                COALESCE(STRING_AGG(pi.image_url, ','), '') AS product_images,
                COALESCE(u.contact, '') AS contact,
                COALESCE(u.city, '') AS city
            FROM products p
            LEFT JOIN product_images pi ON pi.product_id = p.id
            LEFT JOIN users u ON u.id = p.user_id
            WHERE p.id = :product_id
            GROUP BY 
            p.id, p.title, p.description, p.price, p.unit, p.user_id, p.created_at, u.contact, u.city
            """), 
            {
                "product_id": product_id
            })
        
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Product not found")
        await db.commit()
        column_names = result.keys()
        return dict(zip(column_names, row))

    except Exception as e:
        await db.rollback()
        for filename in uploaded_files:
            await delete_file_from_storage(current_user.get("user_id"), filename)
        raise HTTPException(status_code=500, detail=str(e))
