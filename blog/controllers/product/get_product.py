from fastapi import  status, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from ... import schemas
from blog.database import get_async_db
from .route import productRoute


@productRoute.get('/{product_id}', status_code=status.HTTP_200_OK, response_model=schemas.Products)
async def get_product(product_id: str, db: AsyncSession = Depends(get_async_db)):
    try:
        result = await db.execute( text("""
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
            p.id, p.title, p.description, p.price, p.unit, p.user_id, p.created_at, u.contact, u.city """), 
            {
                "product_id": product_id
            })
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Product not found")
        column_names = result.keys()
        return dict(zip(column_names, row))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))