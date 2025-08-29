from fastapi import  status, Depends, HTTPException,Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from ... import schemas
from blog.database import get_async_db
from .route import productRoute

@productRoute.get('/', status_code=status.HTTP_200_OK, response_model=schemas.AllProducts)
async def get_all_products(offset: int = Query(1, ge=0), limit: int = Query(10, gt=0), db: AsyncSession = Depends(get_async_db)):
    try:
        total_stmt = text("SELECT COUNT(*) FROM products")
        total_result = await db.execute(total_stmt)
        total_count = total_result.scalar()

        cal_offset = (offset - 1) * limit
        
        result = await db.execute(text("""
            SELECT 
                p.id AS product_id,
                p.title,
                p.description,
                p.price,
                p.unit,
                p.user_id,
                COALESCE(STRING_AGG(pi.image_url, ','), '') AS product_images,
                p.created_at
            FROM products p
            LEFT JOIN product_images pi ON p.id = pi.product_id
            GROUP BY 
                p.id, p.title, p.description, p.price, p.unit, p.user_id, p.created_at
            ORDER BY p.created_at DESC
            OFFSET :offset ROWS
            FETCH NEXT :limit ROWS ONLY
        """), {
            "offset": cal_offset,
            "limit": limit,
            "order": "DSC"
        })
        
        products = [dict(row._mapping) for row in result.fetchall()]

        if products:
            return schemas.AllProducts(products=products, numb_found=total_count) 
        
        return schemas.AllProducts(products=[], numb_found=0)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
