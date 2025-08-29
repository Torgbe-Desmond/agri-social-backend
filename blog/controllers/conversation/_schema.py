
from pydantic import BaseModel
from typing import Optional, List,Any
from datetime import datetime
from uuid import UUID

class ConversationCreate(BaseModel):
    name: Optional[str]
    is_group: Optional[int] 
    member_ids: List[UUID]

class MessageCreate(BaseModel):
    conversation_id: UUID
    sender_id: UUID
    content: str

class MessageOut(BaseModel):
    id: UUID
    conversation_id:UUID
    sender_id: UUID
    content: str
    username:Optional[str] = None
    images:Optional[str] = None
    videos:Optional[str] = None
    user_image:Optional[str] = None
    created_at: datetime
    
     
class SharedConversationUser(BaseModel):
    user_id: UUID
    username: str
    conversation_id:UUID
    user_image: Optional[str]
    last_message: Optional[str]
    reference_id:UUID
    created_at: Optional[datetime]
    
class SharedConversationGroup(BaseModel):
    conversation_id: UUID
    group_name: Optional[str]
    last_message: Optional[str]
    created_at: Optional[datetime]