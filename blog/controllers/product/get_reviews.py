from fastapi import  status, Depends, HTTPException, Request, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import uuid
from ... import schemas
from blog.database import get_async_db
from .route import productRoute

@productRoute.get('/products/reviews/{product_id}', status_code=status.HTTP_200_OK, response_model=schemas.AllReviews)
async def get_reviews(
    product_id: str, 
    offset: int = Query(0, ge=0),   
    limit: int = Query(10, gt=0),
    db: AsyncSession = Depends(get_async_db)
):
    try:
      # Count the number of reviews
      count_stmt = text("""
          SELECT COUNT(*)
          FROM review r
          WHERE r.product_id = :product_id
      """)
      count_result = await db.execute(count_stmt, {"product_id": product_id})
      total_count = count_result.scalar() or 0
      # Pagination
      cal_offset = offset * limit
      # Fetch reviews
      result = await db.execute(
          text("""
              SELECT 
                  r.id,
                  r.content,
                  r.created_at,
                  r.user_id,
                  r.product_id
              FROM review r
              WHERE r.product_id = :product_id
              ORDER BY r.created_at DESC
              OFFSET :offset ROWS
              FETCH NEXT :limit ROWS ONLY;
          """),
          {
              "product_id": product_id,
              "offset": cal_offset,
              "limit": limit
          }
      )
      
      reviews = [dict(row._mapping) for row in await result.fetchall()]
      
      return schemas.AllReviews(
          reviews=reviews,
          numb_found=total_count
      )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))