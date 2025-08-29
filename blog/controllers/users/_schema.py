
from pydantic import BaseModel
from typing import Optional, List,Any
from datetime import datetime
from uuid import UUID

class UserCreate(BaseModel):
    username: str
    email: str
    password_hash: str

class User(BaseModel):
    id: UUID  
    username: str
    email: str
    created_at: datetime
    notification_count:int
    city:Optional[str] = None
    reference_id:UUID
    firstname:Optional[str] = None
    lastname:Optional[str] = None
    user_image:Optional[str]=None
    followers:Optional[int] = None
    following:Optional[int]=None

class AnotherUser(BaseModel):
    id: UUID 
    username: str
    email: str
    created_at: datetime
    city:Optional[str] = None
    reference_id:UUID
    firstname:Optional[str] = None
    lastname:Optional[str] = None
    user_image:Optional[str]=None
    followers:Optional[int] = None
    following:Optional[int]=None