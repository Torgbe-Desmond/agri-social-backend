from pydantic import BaseModel
from typing import Optional, List,Any
from datetime import datetime
from uuid import UUID

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
    

class Reviews(BaseModel):
    id:UUID
    content:str 
    user_id:UUID
    product_id:UUID
    created_at:datetime

class AllReviews(BaseModel):
    reviews:List[Reviews]
    numb_found:int