from fastapi import APIRouter, Query, HTTPException, File, UploadFile, Form, Depends, status,Request
from .. import schemas
from sqlalchemy import text
from ..database.models import user_table, predictions_history_table
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from blog.database import get_async_db
from ..utils.firebase_interactions import upload_file_to_storage, delete_file_from_storage
from ..utils.stored_procedure_strings import _get_user_profile
from ..utils import send_email_to_recipient,generate_random_string
from ..middleware.authMiddleware import create_access_token,verify_access_token
import uuid
import bcrypt
from datetime import timedelta,datetime,timezone
router = APIRouter()




@router.get('/user/authenticated'   )
async def get_profile_by_user_id():    
    return {"status":True} 


@router.get('/user/profile')
async def get_user_profile(
    username: str = Query(...),
    offset: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db)
):
    try:
        # Search users
        # username = username.join("+")
        print(username)
        
        user_stmt = text("""
            SELECT id, username, user_image 
            FROM users 
            WHERE username ILIKE :username
            LIMIT :limit OFFSET :offset
        """)
        user_result = await db.execute(user_stmt, {
            "username": f"%{username}%", "limit": limit, "offset": offset
        })
        user_rows = user_result.fetchall()
        users = [
            {
                "type": "user",
                "user_id": row.id,
                "username": row.username,
                "image": row.user_image,
            }
            for row in user_rows
        ]

        # Search posts
        post_stmt = text("""
            SELECT p.id , u.username, p.content, u.user_image
            FROM posts p
            JOIN users u ON u.id = p.user_id
            WHERE p.content ILIKE :content
            LIMIT :limit OFFSET :offset
        """)
        post_result = await db.execute(post_stmt, {
            "content": f"%{username}%", "limit": limit, "offset": offset
        })
        post_rows = post_result.fetchall()
        posts = [
            {
                "type": "post",
                "post_id": row.id,
                "username": row.username,
                "content": row.content,
                "image": row.user_image if row.user_image else None,
            }
            for row in post_rows
        ]
        
        # Search comments
        comment_stmt = text("""
            SELECT c.id , u.username, c.content, u.user_image
            FROM comments c
            JOIN users u ON u.id = c.user_id
            WHERE c.content ILIKE :content
            LIMIT :limit OFFSET :offset
        """)
        comment_result = await db.execute(comment_stmt, {
            "content": f"%{username}%", "limit": limit, "offset": offset
        })
        comment_rows = comment_result.fetchall()
        comments = [
            {
                "type": "comment",
                "comment_id": row.id,
                "username": row.username,
                "content": row.content,
                "image": row.user_image if row.user_image else None,
            }
            for row in comment_rows
        ]

        # Search groups
        # group_stmt = text("""
        #     SELECT id, group_name as username, group_icon as image
        #     FROM groups
        #     WHERE group_name ILIKE :group_name
        #     LIMIT :limit OFFSET :offset
        # """)
        # group_result = await db.execute(group_stmt, {
        #     "group_name": f"%{username}%", "limit": limit, "offset": offset
        # })
        # group_rows = group_result.fetchall()
        # groups = [
        #     {
        #         "type": "group",
        #         "id": row.id,
        #         "username": row.username,
        #         "image": row.image,
        #     }
        #     for row in group_rows
        # ]

        all_results = users + posts + comments

        if not all_results:
            raise HTTPException(status_code=404, detail="No results found")

        return all_results

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    
@router.get('/profile/{user_id}', response_model=schemas.User)
async def get_profile_by_user_id(user_id:str, db: AsyncSession = Depends(get_async_db)):
    result = await db.execute(_get_user_profile, {"userId": user_id})
    user = result.mappings().fetchone()

    if not user:
        raise HTTPException(status_code=404, detail="No users found")

    return user 

@router.get('/user', response_model=schemas.User)
async def get_user(request:Request, db: AsyncSession = Depends(get_async_db)):
    current_user = request.state.user 
    result = await db.execute(_get_user_profile, {"userId": current_user.get("user_id")})
    user = result.mappings().fetchone()

    if not user:
        raise HTTPException(status_code=404, detail="No users found")

    return user  # ✅ This is now a dict that matches your schema



@router.get('/user/suggested', response_model=schemas.AllFollowers)
async def get_suggested_users_to_follow(
    request: Request,
    offset: int = Query(1, ge=1),
    limit: int = Query(3, gt=0),
    db: AsyncSession = Depends(get_async_db)
):
    try:
        current_user = request.state.user

        # Get total count
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

        # Get followers
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
        followers_raw = result.fetchall()

        # Convert each Row to a dict, then to Follower
        followers = [
            schemas.Follower(
                id=row.id,
                firstname=row.firstname,
                lastname=row.lastname,
                username=row.username,
                user_image=row.user_image
            )
            for row in followers_raw
        ]

        return schemas.AllFollowers(followers=followers, numb_found=total_count)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/user/image")
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


@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def register(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_async_db)
):
    try:
        # Check if username exists
        username_check = await db.execute(
            text("SELECT EXISTS(SELECT 1 FROM users WHERE username = :username)"),
            {"username": username}
        )
        if username_check.scalar():
            raise HTTPException(status_code=400, detail="Username already exists")

        # Check if email exists
        email_check = await db.execute(
            text("SELECT EXISTS(SELECT 1 FROM users WHERE email = :email)"),
            {"email": email}
        )
        if email_check.scalar():
            raise HTTPException(status_code=400, detail="Email already exists")

        # Hash the password
        hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        # Create new user
        result = await db.execute(
            text("""
                INSERT INTO users (username, email, password_hash, created_at)
                VALUES (:username, :email, :password_hash, NOW())
                RETURNING id, username, email
            """),
            {"username": username, "email": email, "password_hash": hashed_password}
        )
        await db.commit()

        new_user = result.fetchone()
        return {"id": new_user.id, "username": new_user.username, "email": new_user.email}

    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")



@router.put('/user/update')
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



@router.post("/auth/login")
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

        if not bcrypt.checkpw(password.encode("utf-8"), user.password_hash.encode("utf-8")):
            raise HTTPException(status_code=401, detail="Wrong email or password")

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


@router.post("/follow") 
async def toggle_follow(request:Request,user_id: str = Form(...), db: AsyncSession = Depends(get_async_db)):
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


@router.post("/auth/send-verification-email", status_code=status.HTTP_200_OK, response_model=schemas.SuccessResponse)
async def send_email_for_verification(
    email: str = Form(...),
    db: AsyncSession = Depends(get_async_db)
):
    try:
        # Check if user exists
        result = await db.execute(
            text("SELECT * FROM users WHERE email = :email"),
            {"email": email}
        )
        user = result.fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="No such user")

        verification_string = generate_random_string()
        verification_expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

        # Save string and expiry
        await db.execute(
            text("""
                UPDATE users
                SET verification_string = :verification_string,
                    verification_expires_at = :expires_at
                WHERE id = :user_id
            """),
            {
                "verification_string": verification_string,
                "expires_at": verification_expires_at,
                "user_id": user.id
            }
        )

        # Prepare verification email
        url = ["https://student-rep.vercel.app", "http://localhost:3000"]
        verification_data = {
            "username": user.username,
            "to": [user.email],
            "subject": "Agrisocial Email Verification",
            "verification_link": f"{url[1]}/{verification_string}/update-password/"
        }

        await send_email_to_recipient(verification_data)

        await db.commit()

        return schemas.SuccessResponse(
            success=True,
            message="Visit your email to verify password",
            data=None
        )

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/auth/update-password", response_model=schemas.SuccessResponse)
async def update_password(
    verification_string: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_async_db),
):
    try:
        if not password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please enter password"
            )

        # Check user and expiry
        result = await db.execute(
            text("""
                SELECT id, verification_expires_at
                FROM users
                WHERE verification_string = :verification_string
            """),
            {"verification_string": verification_string}
        )
        user = result.fetchone()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid verification link"
            )

        # Check expiry
        if not user.verification_expires_at or datetime.now(timezone.utc) > user.verification_expires_at:
            raise HTTPException(status_code=400, detail="Verification link expired")

        hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        # Update password & clear verification string
        await db.execute(
            text("""
                UPDATE users
                SET password_hash = :password_hash,
                    verification_string = NULL,
                    verification_expires_at = NULL
                WHERE id = :user_id
            """),
            {"password_hash": hashed_password, "user_id": user.id}
        )

        await db.commit()

        return schemas.SuccessResponse(
            success=True,
            message="Password update was successful",
            data=None
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error occurred: {str(e)}"
        )

        

@router.get("/auth/generate-verification-token/{verification_string}", response_model=schemas.SuccessResponse)
async def generate_token_for_verification(verification_string: str, db: AsyncSession = Depends(get_async_db)):
    try:
        if not verification_string:
             raise HTTPException(
                 status_code=status.HTTP_400_BAD_REQUEST,
                 detail="Reference ID is required"
             )
        
         # Fetch user details
        result = await db.execute(
             text("""
                 SELECT id, username, reference_id
                 FROM users
                 WHERE verification_string = :verification_string
             """),
             {"verification_string": verification_string}
         )
        user = result.fetchone()
    
        if not user:
            raise HTTPException(
                status_code=401,
                detail="Unauthorized"
            )
    
        # Create JWT token with 5 min expiry
        token = create_access_token(
            data={
                 "user_id": str(user.id),
                 "username": user.username,
                 "reference_id": str(user.reference_id)
             },
             expires_delta=timedelta(minutes=5)
         )
        
        return schemas.SuccessResponse(
             success=True,
             message="Token generated successfully",
             data={"verification_token": token}
         )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )