from pydantic import BaseModel
from typing import Optional, List,Any
from datetime import datetime
from uuid import UUID

class CommentCreate(BaseModel):
    post_id: UUID
    user_id: UUID
    content: str
    created_at: datetime
    
class Comment(BaseModel):
    id: UUID
    post_id: UUID
    user_id: UUID
    likes:int
    liked:Optional[bool] = None
    saved:Optional[bool] = None
    videos:Optional[str] = None
    has_vide:Optional[int] = None
    images:Optional[str] = None
    username:str
    content: str
    tags:Optional[str] = None
    replies:int
    created_at: datetime
    user_image:Optional[str] = None
    parent_id:Optional[str] = None
    
class AllComment(BaseModel):
    comments:List[Comment]
    numb_found:int