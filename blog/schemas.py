from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID


# ---------------------- Users ----------------------
class UserCreate(BaseModel):
    username: str
    email: str
    password_hash: str

class User(BaseModel):
    id: UUID  # ← change this from str to UUID
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

    
# ---------------------- Posts ----------------------
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
    saved: int
    liked:Optional[bool] = None
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

# ---------------------- PostVideos ----------------------
class PostVideoCreate(BaseModel):
    post_id: UUID
    video_url: str

class PostVideo(BaseModel):
    id: UUID
    post_id: UUID
    video_url: str

# ---------------------- PostImages ----------------------
class PostImageCreate(BaseModel):
    post_id: str
    image_url: str

class PostImage(BaseModel):
    id: UUID
    post_id: UUID
    image_url: str



# ---------------------- Predictions ----------------------

class PredictionCreate(BaseModel):
    user_id: UUID
    image_url: str
    prediction_label: Optional[str] = None
    confidence: Optional[float] = None

class Prediction(BaseModel):
    id: UUID
    user_id: UUID
    image_url: str
    prediction_label: Optional[str]
    confidence: Optional[float]
    created_at: datetime
    generated_name:Optional[str] = None

class AllPrediction(BaseModel):
     notifications:List[Prediction]
     numb_found:int
    
# ---------------------- PredictionHistory ----------------------
class PredictionHistoryCreate(BaseModel):
    user_id: UUID
    prediction_id: UUID

class PredictionHistory(BaseModel):
    id: UUID
    user_id: UUID
    prediction_id: UUID
    reviewed_at: datetime
    
# ---------------------- Comments ----------------------

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
    username:str
    content: str
    replies:int
    created_at: datetime
    user_image:Optional[str] = None
    parent_id:Optional[str] = None
    
class AllComment(BaseModel):
    comments:List[Comment]
    numb_found:int
    
# ---------------------- Comments ----------------------


    
    
# ---------------------- notifications ----------------------
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
    
# ---------------------- notifications ----------------------
class AllNotifications(BaseModel):
     notifications:List[Notifications]
     numb_found:int

    
# ---------------------- Search ----------------------
class Search(BaseModel):
    id:UUID
    user_image:Optional[str] = None
    username:str
    num_found:int
    
    
# ---------------------- PostVideos ----------------------
class Follower(BaseModel):
    id:UUID
    username:Optional[str] = None
    lastname:Optional[str] = None
    firstname:Optional[str] = None
    user_image:Optional[str] = None
    
class AllFollowers(BaseModel):
    followers:List[Follower]
    numb_found:int
    
    
# ---------------------- Products ----------------------

class Products(BaseModel):
    product_id:UUID
    title:str 
    description:Optional[str] = None
    price:str
    unit:Optional[str] = None
    user_id:UUID
    contact:Optional[str] = None
    city:Optional[str] = None
    product_images:Optional[str] = None
    created_at:datetime

class AllProducts(BaseModel):
    products:List[Products]
    numb_found:int

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

    
    
# "(sqlalchemy.dialects.postgresql.asyncpg.ProgrammingError) <class 'asyncpg.exceptions.UndefinedFunctionError'>: function isnull(character varying, unknown) does not exist
# HINT:  No function matches the given name and argument types. You might need to add explicit type casts.
# [SQL: 
#     SELECT 
#         p.id AS post_id,
#         p.content,
#         p.created_at,
#         p.user_id,
#         ISNULL((SELECT user_image FROM users WHERE id = p.user_id), '') AS user_image,
#         (SELECT COUNT(*) FROM post_likes WHERE post_id = p.id) AS likes,
#         (SELECT COUNT(*) FROM saved_posts WHERE post_id = p.id) AS saved,
#         (SELECT COUNT(*) FROM comments WHERE post_id = p.id) AS comments,
#         ISNULL((SELECT STRING_AGG(image_url, ',') FROM post_images WHERE post_id = p.id), '') AS images,
#         ISNULL((SELECT STRING_AGG(tag_name, ',') FROM tags WHERE post_id = p.id), '') AS tags,
#         ISNULL((SELECT STRING_AGG(video_url, ',') FROM post_videos WHERE post_id = p.id), '') AS videos,
#         (SELECT username FROM users WHERE id = p.user_id) AS username
#     FROM posts p
#     WHERE p.id = $1
# ]
# [parameters: ('87b320b4-123d-4bfb-8021-015a6620cf42',)]
# (Background on this error at: https://sqlalche.me/e/20/f405)"





