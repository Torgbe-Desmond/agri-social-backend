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

@productRoute.put('/{product_id}', status_code=status.HTTP_200_OK)
async def update_product(
    product_id: str,
    request:Request,
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    image_id: str = Form(...),
    price: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    oldPrice: Optional[str] = Form(None),
    unit: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_async_db)
):
    try:
        current_user = request.state.user
        fields = []
        values = {"product_id": product_id}

        if title is not None:
            fields.append("title = :title")
            values["title"] = title
        if description is not None:
            fields.append("description = :description")
            values["description"] = description
        if price is not None:
            fields.append("price = :price")
            values["price"] = price
        if oldPrice is not None:
            fields.append("oldPrice = :oldPrice")
            values["oldPrice"] = oldPrice
        if unit is not None:
            fields.append("unit = :unit")
            values["unit"] = unit

        if not fields:
            raise HTTPException(status_code=400, detail="No fields provided for update.")

        if file:
            content_type = file.content_type
            file_bytes = await file.read()
            file_name = file.filename
            extension = file_name.split('.')[-1]
            generated_name = f"plant.disease.detection.{generate_random_string()}.{extension}"
            file_url = await upload_file_to_storage(current_user.get("user_id"), generated_name, file_bytes, content_type)
            if not file_url:
                raise HTTPException(status_code=500, detail="Error uploading file")

            await db.execute(text("""
                UPDATE product_images SET image_url = :image_url WHERE id = :image_id
            """), {
                "image_url": file_url,
                "image_id": image_id
            })

        update_stmt = text(f"""
            UPDATE products
            SET {', '.join(fields)}
            WHERE id = :product_id
        """)
        result = await db.execute(update_stmt, values)
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Product not found.")

        await db.commit()
        return {"message": "Product updated successfully."}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


