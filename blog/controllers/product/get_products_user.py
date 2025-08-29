from fastapi import  status, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from ... import schemas
from blog.database import get_async_db
from .route import productRoute

@productRoute.get('/user/', status_code=status.HTTP_200_OK, response_model=schemas.AllProducts)
async def get_products_user(request:Request, db: AsyncSession = Depends(get_async_db)):
    try:
        current_user = request.state.user
        
        count_stmt = text("SELECT COUNT(*) FROM products WHERE user_id =:user_id")
        result = await db.execute(
            count_stmt,
            {"user_id": current_user.get("user_id")}
        )        
        total_count = result.scalar()
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
            LEFT JOIN product_images pi ON pi.product_id = p.id
            WHERE p.user_id = :user_id
            GROUP BY 
            p.id, p.title, p.description, p.price, p.unit, p.user_id, p.created_at
            """), 
            {
                "user_id": current_user.get("user_id")
            })
        products = [dict(row._mapping) for row in result.fetchall()]
        
        if products:
            return schemas.AllProducts(products=products,numb_found=total_count)
        
        return schemas.AllProducts(products=[],numb_found=0)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))