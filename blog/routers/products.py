from fastapi import APIRouter, status, Form, Depends, HTTPException, UploadFile, File, Query,Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import uuid

from .. import schemas
from ..utils.firebase_interactions import upload_file_to_storage,delete_file_from_storage
from ..utils import generate_random_string
from blog.database import get_async_db
from ..utils.stored_procedure_strings import _get_product, _get_product_history, _get_all_products,_get_product

router = APIRouter()

@router.get('/products/{product_id}', status_code=status.HTTP_200_OK, response_model=schemas.Products)
async def get_product(product_id: str, db: AsyncSession = Depends(get_async_db)):
    try:
        result = await db.execute(_get_product, {"product_id": product_id})
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Product not found")
        column_names = result.keys()
        return dict(zip(column_names, row))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@router.get('/products/reviews/{product_id}', status_code=status.HTTP_200_OK, response_model=schemas.AllReviews)
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
                  r.product_id,
                  u.user_image,
                  u.username
              FROM review r
              JOIN users u ON u.id = r.user_id
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

        reviews = [dict(row._mapping) for row in  result.fetchall()] 

        return schemas.AllReviews(
            reviews=reviews,
            numb_found=total_count
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post(
    "/products/reviews", 
    status_code=status.HTTP_201_CREATED, 
    response_model=schemas.Reviews
)
async def create_review(
    request: Request,
    product_id: str=Form(...), 
    content: str = Form(...),
    hav_video: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_async_db)
):
    try:
        current_user = request.state.user

        # Insert review and get back the new review ID
        insert_stmt = text("""
            INSERT INTO review (product_id, user_id, content)
            VALUES (:product_id, :user_id, :content)
            RETURNING id
        """)
        insert_result = await db.execute(insert_stmt, {
            "product_id": product_id,
            "user_id": current_user.get("user_id"),
            "content": content,
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
                    r.user_id,
                    u.user_image,
                    u.username
                FROM review r
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
            username=created_review.username,
            user_image=created_review.user_image,
            user_id=created_review.user_id,
        )

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

     

@router.get('/user-products/', status_code=status.HTTP_200_OK, response_model=schemas.AllProducts)
async def get_products_user(request:Request, db: AsyncSession = Depends(get_async_db)):
    try:
        current_user = request.state.user
        
        count_stmt = text("SELECT COUNT(*) FROM products WHERE user_id =:user_id")
        result = await db.execute(
            count_stmt,
            {"user_id": current_user.get("user_id")}
        )        
        total_count = result.scalar()
        result = await db.execute(_get_product_history, {"user_id": current_user.get("user_id")})
        products = [dict(row._mapping) for row in result.fetchall()]
        
        if products:
            return schemas.AllProducts(products=products,numb_found=total_count)
        
        return schemas.AllProducts(products=[],numb_found=0)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/products', status_code=status.HTTP_200_OK, response_model=schemas.AllProducts)
async def get_all_products(offset: int = Query(1, ge=0), limit: int = Query(10, gt=0), db: AsyncSession = Depends(get_async_db)):
    try:
        total_stmt = text("SELECT COUNT(*) FROM products")
        total_result = await db.execute(total_stmt)
        total_count = total_result.scalar()

        cal_offset = (offset - 1) * limit
        result = await db.execute(_get_all_products, {
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



@router.get('/products/search', status_code=status.HTTP_200_OK)
async def search_products(query: str, db: AsyncSession = Depends(get_async_db)):
    try:
        search_stmt = text("""
            SELECT * FROM products 
            WHERE title LIKE :query OR description LIKE :query
        """)
        result = await db.execute(search_stmt, {"query": f"%{query}%"})
        return [dict(row._mapping) for row in result.fetchall()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.post('/products', status_code=status.HTTP_200_OK, response_model=schemas.Products)
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
    uploaded_files = []  # track uploaded file names
    try:
        current_user = request.state.user
        # Insert product and return its ID
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
            # "oldPrice": oldPrice,
            "unit": unit,
            "user_id": current_user.get("user_id")
        })
        product_id = result.scalar_one()

        # Handle image uploads
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

        # Fetch and return the newly created product
        result = await db.execute(_get_product, {"product_id": product_id})
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Product not found")
        await db.commit()
        column_names = result.keys()
        return dict(zip(column_names, row))

    except Exception as e:
        await db.rollback()
        # Clean up any uploaded files
        for filename in uploaded_files:
            await delete_file_from_storage(current_user.get("user_id"), filename)
        raise HTTPException(status_code=500, detail=str(e))


@router.put('/products/{product_id}', status_code=status.HTTP_200_OK)
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


@router.delete('/products/{product_id}', status_code=status.HTTP_200_OK)
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

# "(sqlalchemy.dialects.postgresql.asyncpg.Error) <class 'asyncpg.exceptions.DataError'>: invalid input for query argument $1: 'user' (invalid UUID 'user': length must be between 32..36 characters, got 4)\n[SQL: \n    SELECT \n        p.id AS product_id,\n        p.title,\n        p.description,\n        p.price,\n        p.unit,\n        p.user_id,\n        p.created_at,\n        COALESCE(STRING_AGG(pi.image_url, ','), '') AS product_images,\n        COALESCE(u.contact, '') AS contact,\n        COALESCE(u.city, '') AS city\n    FROM products p\n    LEFT JOIN product_images pi ON pi.product_id = p.id\n    LEFT JOIN users u ON u.id = p.user_id\n    WHERE p.id = $1\n    GROUP BY \n        p.id, p.title, p.description, p.price, p.unit, p.user_id, p.created_at, u.contact, u.city\n]\n[parameters: ('user',)]\n(Background on this error at: https://sqlalche.me/e/20/dbapi)"



