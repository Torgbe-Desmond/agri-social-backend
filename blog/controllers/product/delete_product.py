from fastapi import  status, Depends, HTTPException,Query,Form,Request,File,UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from blog.database import get_async_db
from .route import productRoute

@productRoute.delete('/products/{product_id}', status_code=status.HTTP_200_OK)
async def delete_product(product_id: str, db: AsyncSession = Depends(get_async_db)):
    try:
        delete_stmt = text("DELETE FROM products WHERE id = :product_id")
        result = await db.execute(delete_stmt, {"product_id": product_id})
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Product not found.")
        await db.commit()
        return {"product_id": product_id}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))