from fastapi import APIRouter, Query, HTTPException, File, UploadFile, Form, Depends, status
from ..controllers.users import get_all_users
from .. import schemas

router = APIRouter()

# @router.get('/user/{user_id}', response_model=schemas.User)
# get_all_users()