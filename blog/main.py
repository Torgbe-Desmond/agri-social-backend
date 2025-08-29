# pyright: ignore[reportMissingImports]
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .socket_manager import sio, socket_app
# from .controllers.users import route as userRoute
# from .controllers.authentication import route as authRoute
# from .controllers.comment import route as commentRoute
# from .controllers.post import route as postRoute
# from .controllers.notification import route as notificationRoute
# from .controllers.conversation import route as conversationRoute
# from .controllers.product import route as productRoute
# from .controllers.prediction import route as predictionRoute
from .middleware.authMiddleware import AuthMiddleware

# from .routers import predictionRoute,productRoute, conversationRoute,notificationRoute,postRoute,commentRoute,authRoute,userRoute

from .routers import predictions, post,user, comment, likes, saved, notifications, products, messages

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

# app.include_router(userRoute.userRoute)
# app.include_router(authRoute.authRoute)
# app.include_router(commentRoute.commentRoute)
# app.include_router(postRoute.postRoute)
# app.include_router(notificationRoute.notificationRoute)
# app.include_router(conversationRoute.conversationRoute)
# app.include_router(productRoute.productRoute)
# app.include_router(predictionRoute.predictionRoute)

app.include_router(user.router)
app.include_router(post.router)
app.include_router(predictions.router)
app.include_router(comment.router)
app.include_router(likes.router)
app.include_router(saved.router)
app.include_router(notifications.router)
app.include_router(products.router)
app.include_router(messages.router)


for routed in app.routes:
    print(routed.path)



