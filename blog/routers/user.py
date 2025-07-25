from fastapi import APIRouter, Query, HTTPException, File, UploadFile, Form, Depends, status,Request
from .. import schemas
from sqlalchemy import text
from ..database.models import user_table, predictions_history_table
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from blog.database import get_async_db
from ..utils.firebase_interactions import upload_file_to_storage, delete_file_from_storage
from ..utils.stored_procedure_strings import _get_user_profile
from ..middleware.authMiddleware import create_access_token,verify_access_token
import uuid
import bcrypt

router = APIRouter()

@router.get('/user-profile', response_model=List[schemas.Search])
async def get_user_profile( username: str = Query(...), db: AsyncSession = Depends(get_async_db)):
    query_stmt = text("SELECT id, username, user_image FROM users WHERE username LIKE :username")
    result = await db.execute(query_stmt, {"username": f"%{username}%"})
    rows = result.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="No users found")

    users = [
        {
            "user_image": row.user_image,
            "username": row.username,
            "id": row.id,
            "num_found": len(rows)
        }
        for row in rows
    ]
    return users


@router.get('/user', response_model=schemas.User)
async def get_user(request:Request, db: AsyncSession = Depends(get_async_db)):
    current_user = request.state.user 
    result = await db.execute(_get_user_profile, {"userId": current_user.get("user_id")})
    user = result.mappings().fetchone()

    if not user:
        raise HTTPException(status_code=404, detail="No users found")

    return user  # ✅ This is now a dict that matches your schema


@router.get('/another-user/{user_id}', response_model=schemas.User)
async def get_user(user_id:str, db: AsyncSession = Depends(get_async_db)):
    result = await db.execute(_get_user_profile, {"userId": user_id})
    user = result.mappings().fetchone()

    if not user:
        raise HTTPException(status_code=404, detail="No users found")

    return user  # ✅ This is now a dict that matches your schema


@router.get('/new-followers', response_model=schemas.AllFollowers)
async def get_more_active_followers(
    request:Request,
    offset: int = Query(1, ge=1),
    limit: int = Query(3, gt=0),
    db: AsyncSession = Depends(get_async_db)
):
    try:
        current_user = request.state.user 
        get_followers_count_stmt = text("""
            SELECT COUNT(*) 
            FROM users 
            WHERE id != :user_id AND id NOT IN (
                SELECT following_id 
                FROM followers 
                WHERE follower_id = :user_id
            )
        """)
        total_count_result = await db.execute(get_followers_count_stmt, {"user_id": current_user.get("user_id")})
        total_count = total_count_result.scalar()

        cal_offset = (offset - 1) * limit

        get_followers_stmt = text("""
            SELECT id, firstname, lastname, username, user_image 
            FROM users 
            WHERE id != :user_id AND id NOT IN (
                SELECT following_id 
                FROM followers 
                WHERE follower_id = :user_id
            )
            ORDER BY created_at DESC
            OFFSET :offset ROWS
            FETCH NEXT :limit ROWS ONLY
        """)

        result = await db.execute(get_followers_stmt, {
            "user_id": current_user.get("user_id"),
            "offset": cal_offset,
            "limit": limit
        })
        followers = result.fetchall()

        return schemas.AllFollowers(followers=followers, numb_found=total_count)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/update-user-profile-image")
async def update_user_profile(request:Request, file: UploadFile = File(...), db: AsyncSession = Depends(get_async_db)):
    file_name = file.filename
    try:
        current_user = request.state.user         
        content_type = file.content_type
        file_bytes = await file.read()

        file_url = await upload_file_to_storage(current_user.get("user_id"), file_name, file_bytes, content_type)
        if not file_url:
            raise HTTPException(status_code=500, detail="Failed to upload image")

        update_stmt = text("UPDATE users SET user_image = :user_image WHERE id = :user_id")
        await db.execute(update_stmt, {"user_image": file_url, "user_id": current_user.get("user_id")})
        await db.commit()

        return "Upload was successful"

    except Exception as e:
        await delete_file_from_storage(current_user.get("user_id"), file_name)
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=schemas.User)
async def register(username: str = Form(...),email: str = Form(...),password: str = Form(...), db: AsyncSession = Depends(get_async_db)):
    try:
        # Check if username exists
        username_check = await db.execute(
            text("SELECT 1 FROM users WHERE username = :username"),
            {"username": username}
        )
        if username_check.scalar():
            raise HTTPException(status_code=400, detail="Username not available")

        # Check if email exists
        email_check = await db.execute(
            text("SELECT 1 FROM users WHERE email = :email"),
            {"email": email}
        )
        if email_check.scalar():
            raise HTTPException(status_code=400, detail="Email already exists")

        # Hash the password
        hashed_password = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        # Create new user
        await db.execute(text("""
            INSERT INTO users (username, email, password_hash, created_at)
            VALUES ( :username, :email, :password_hash, NOW())
        """), {
            "username": username,
            "email": email,
            "password_hash": hashed_password
        })

        await db.commit()

        return {"message":"Registration was successful"}

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.put('/update-user')
async def update_user(
    request:Request,
    username: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    city: Optional[str] = Form(None),
    contact: Optional[str] = Form(None),
    firstname: Optional[str] = Form(None),
    lastname: Optional[str] = Form(None),
    interests: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_async_db),
):
    try:
        current_user = request.state.user         
        fields_to_update = []
        values = {"user_id": current_user.get("user_id")}
        if username:
            fields_to_update.append("username = :username")
            values["username"] = username
        if email:
            fields_to_update.append("email = :email")
            values["email"] = email
        if city:
            fields_to_update.append("city = :city")
            values["city"] = city
        if contact:
            fields_to_update.append("contact = :contact")
            values["contact"] = contact
        if firstname:
            fields_to_update.append("firstname = :firstname")
            values["firstname"] = firstname
        if lastname:
            fields_to_update.append("lastname = :lastname")
            values["lastname"] = lastname

        if fields_to_update:
            query = f"""
                UPDATE users
                SET {', '.join(fields_to_update)}
                WHERE id = :user_id
            """
            await db.execute(text(query), values)

        if interests:
            split_interests = [i.strip() for i in interests.split(",") if i.strip()]
            for interest in split_interests:
                check_stmt = text("""
                    SELECT 1 FROM user_interests 
                    WHERE user_id = :user_id AND interest = :interest
                """)
                result = await db.execute(check_stmt, {"user_id": current_user.get("user_id"), "interest": interest})
                if not result.fetchone():
                    interest_id = str(uuid.uuid4())
                    insert_stmt = text("""
                        INSERT INTO user_interests (id, user_id, interest, created_at)
                        VALUES (:id, :user_id, :interest, GETDATE())
                    """)
                    await db.execute(insert_stmt, {"id": interest_id, "user_id": current_user.get("user_id"), "interest": interest})

        await db.commit()
        return {"message": "User updated successfully."}

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))




@router.post("/login")
async def login(
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_async_db)
):
    try:
        result = await db.execute(text("SELECT * FROM users WHERE email = :email"), {"email": email})
        user = result.fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="Wrong email or password")

        # if not bcrypt.checkpw(password.encode("utf-8"), user.password_hash.encode("utf-8")):
        #     raise HTTPException(status_code=401, detail="Wrong email or password")

        # ✅ Generate token with user ID and username
        token = create_access_token(data={"user_id": str(user.id), "username": user.username, "reference_id":str(user.reference_id)})

        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id":str(user.id),
                "username": user.username,
                "email": user.email,
                "user_image": user.user_image,
                "reference_id":str(user.reference_id)
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/following/{user_id}")
async def is_following(user_id: str, request:Request, db: AsyncSession = Depends(get_async_db)):
    try:
        current_user = request.state.user
        query = text("""
            SELECT 1 FROM followers
            WHERE following_id = :user_id AND follower_id = :current_user_id
        """)
        result = await db.execute(query, {
            "current_user_id": current_user.get("user_id"),
            "user_id": user_id
        })
        return {"isFollowing": bool(result.fetchone())}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/follow/{user_id}")
async def toggle_follow(user_id: str, request:Request, db: AsyncSession = Depends(get_async_db)):
    try:
        current_user = request.state.user
        result = await db.execute(text("""
            SELECT 1 FROM followers 
            WHERE following_id = :user_id AND follower_id = :localUser
        """), {"localUser": current_user.get("user_id"), "user_id": user_id})

        if result.fetchone():
            await db.execute(text("""
                DELETE FROM followers 
                WHERE following_id = :user_id AND follower_id = :localUser
            """), {"localUser": current_user.get("user_id"), "user_id": user_id})
            is_following = False
        else:
            await db.execute(text("""
                INSERT INTO followers (following_id, follower_id) 
                VALUES (:user_id, :localUser)
            """), {"localUser": current_user.get("user_id"), "user_id": user_id})
            is_following = True

        await db.commit()
        return {"follow": is_following}

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))



