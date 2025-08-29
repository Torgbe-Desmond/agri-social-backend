from pydantic import BaseModel
from typing import Optional, List,Any
from datetime import datetime
from uuid import UUID

class Notifications(BaseModel):
    id:UUID
    user_id:UUID
    actor_id:UUID
    type:str
    entity_id:UUID
    images:Optional[str] = None
    videos:Optional[str] = None    
    entity_type:str
    user_image:str
    username:str
    action_id: Optional[str]= None
    message:str
    is_read:int
    created_at:datetime
    
class AllNotifications(BaseModel):
     notifications:List[Notifications]
     numb_found:int
