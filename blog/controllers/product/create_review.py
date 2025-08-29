from fastapi import  status, Depends, HTTPException, Request, Query,Form
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import uuid
from ... import schemas
from blog.database import get_async_db
from .route import productRoute

@productRoute.post(
    "/products/reviews/{product_id}", 
    status_code=status.HTTP_201_CREATED, 
    response_model=schemas.Reviews
)
async def create_review(
    request: Request,
    product_id: str, 
    content: str = Form(...),
    hav_video: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_async_db)
):
    try:
        current_user = request.state.user

        # Insert review and get back the new review ID
        insert_stmt = text("""
            INSERT INTO reviews (product_id, user_id, content, hav_video)
            VALUES (:product_id, :user_id, :content, :hav_video)
            RETURNING id
        """)
        insert_result = await db.execute(insert_stmt, {
            "product_id": product_id,
            "user_id": current_user.get("user_id"),
            "content": content,
            "hav_video": hav_video
        })
        new_review_id = insert_result.scalar()
        await db.commit()

        # Fetch the created review
        result = await db.execute(
            text("""
                SELECT 
                    r.id,
                    r.product_id,
                    r.content,
                    r.created_at,
                    r.user_id
                FROM reviews r
                JOIN users u ON u.id = r.user_id
                WHERE r.id = :review_id
            """),
            {"review_id": new_review_id}
        )
        created_review = result.fetchone()

        if not created_review:
            raise HTTPException(status_code=400, detail="Error creating review")

        return schemas.Reviews(
            id=created_review.id,
            product_id=created_review.product_id,
            created_at=created_review.created_at,
            content=created_review.content,
            user_id=created_review.user_id,
        )

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

     