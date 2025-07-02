# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .socket_manager import sio, socket_app
from .routers import predictions, user, post, comment, likes, saved, notifications, products, messages

app = FastAPI()

# Attach FastAPI app to socket_app
socket_app.other_asgi_app = app  # ✅ This line is correct and necessary

# --- CORS Setup ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store connected users

# --- Include Routers ---
app.include_router(user.router)
app.include_router(post.router)
app.include_router(predictions.router)
app.include_router(comment.router)
app.include_router(likes.router)
app.include_router(saved.router)
app.include_router(notifications.router)
app.include_router(products.router)
app.include_router(messages.router)


# --- Socket.IO Events ---

