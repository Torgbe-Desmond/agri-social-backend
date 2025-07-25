# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .socket_manager import sio, socket_app
from .controllers.users import route
from .routers import predictions, post,user, comment, likes, saved, notifications, products, messages
from .middleware.authMiddleware import AuthMiddleware

app = FastAPI()

socket_app.other_asgi_app = app 

app.add_middleware(AuthMiddleware)

# --- CORS Setup ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000","https://agri-social.vercel.app/"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# app.include_router(route.userRoute)
app.include_router(user.router)
app.include_router(post.router)
app.include_router(predictions.router)
app.include_router(comment.router)
app.include_router(likes.router)
app.include_router(saved.router)
app.include_router(notifications.router)
app.include_router(products.router)
app.include_router(messages.router)

# for routed in app.routes:
#     print(routed.path)



