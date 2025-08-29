
from pydantic import BaseModel
from typing import Optional, List,Any
from datetime import datetime
from uuid import UUID

class PostCreate(BaseModel):
    user_id: UUID
    content: Optional[str] = None

class Post(BaseModel):
    id: UUID
    user_id: UUID
    content: Optional[str] = None
    created_at: datetime

class GetAllPost(BaseModel):
    post_id: UUID
    content: str
    created_at: datetime
    likes: int
    saves: int
    saves: int
    liked:Optional[bool] = None
    saved:Optional[bool] = None
    saved:Optional[bool] = None
    user_id:UUID
    has_video:Optional[int]
    comments: int
    username:str
    images: Optional[str] = None
    tags: Optional[str] = None
    videos: Optional[str] = None
    user_image:Optional[str]=None

class AllPost(BaseModel):
    posts: List[GetAllPost]
    numb_found:int

class PostVideoCreate(BaseModel):
    post_id: UUID
    video_url: str

class PostVideo(BaseModel):
    id: UUID
    post_id: UUID
    video_url: str

class PostImageCreate(BaseModel):
    post_id: str
    image_url: str

class PostImage(BaseModel):
    id: UUID
    post_id: UUID
    image_url: str
