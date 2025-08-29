from pydantic import BaseModel
from typing import Optional, List,Any
from datetime import datetime
from uuid import UUID

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
     predictions:List[Prediction]
     numb_found:int
    
class PredictionHistoryCreate(BaseModel):
    user_id: UUID
    prediction_id: UUID

class PredictionHistory(BaseModel):
    id: UUID
    user_id: UUID
    prediction_id: UUID
    reviewed_at: datetime