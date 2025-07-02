from fastapi import FastAPI
from typing import Optional
from pydantic import BaseModel
import uvicorn

app = FastAPI()

@app.get('/blog')
def index(limit: int = 10, published: bool = True, sort: Optional[str] = None):
    if published:
        return {"data": f"{limit} published blogs from the database"}
    else:
        return {"data": f"{limit} blogs from the database"}

@app.get('/')
def home():
    return {"data": "Welcome to the homepage"}

@app.get('/about')
def about():
    return {"data": "About page"}

class Blog(BaseModel):
    title: str
    body: str
    published: Optional[bool] = True  # Optional can have a default

@app.post("/blog")
def create_post(request: Blog):
    return {"data": f"blog is created with {request.title}"}


# if __name__ == "__main__":
#     uvicorn(app,host = "127.0.0.1", port= 9000)