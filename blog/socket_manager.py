# app/socket_manager.py
import socketio
from sqlalchemy import text
from .database import async_session  # Adjust based on your actual import
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from .utils.stored_procedure_strings import _view_notifications

# Create Socket.IO server
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=["http://localhost:3000"]
)

# Wrap with ASGIApp
socket_app = socketio.ASGIApp(sio)  # Will attach FastAPI app later
userMap = {}  # Stores user_id -> socket_id mapping

# --- Socket.IO Events ---

def getSocket(user_id):
    print(userMap)
    return userMap.get(user_id)

@sio.event
async def connect(sid, environ):
    print(f"🔌 Connected: {sid}")

@sio.event
async def disconnect(sid):
    print(f"❌ Disconnected: {sid}")
    # Remove disconnected user from userMap
    for uid, stored_sid in list(userMap.items()):
        if stored_sid == sid:
            del userMap[uid]
            print(f"🗑️ Removed {uid} from userMap")
            break

@sio.event
async def chat_message(sid, data):
    print(f"💬 Message from {sid}: {data}")
    await sio.emit("chat_response", {"message": data}, to=sid)

@sio.on("user")
async def user_connection(sid, data):
    user_id = data.get("user_id")
    if user_id:
        userMap[user_id] = sid
        print(f"👤 User connected: {user_id} on socket ID: {sid}")
        print("📌 Current userMap:", userMap)
    else:
        print("⚠️ Missing user_id in connection payload")
        





# ------------------Notification------------------
@sio.on("new_notification")
async def new_notification(sid, data):
    user_id = data.get("user_id")
    print("🔔 new_notification event for:", user_id)
    
    async with async_session() as session:
        try:
            # ✅ Correct: await the session.execute
            result = await session.execute(text("""
                SELECT COUNT(*) 
                FROM notifications
                WHERE user_id = :user_id AND is_read = :is_read
            """), {"user_id": user_id, "is_read": 0})

            # ✅ Get the scalar count value
            notification_count = result.scalar()
            print(notification_count)

            # ✅ Emit to the correct socket ID
            recipient_sid = userMap.get(user_id)
            if recipient_sid:
                await sio.emit("notification_count", {
                    "notification_count": notification_count
                }, to=recipient_sid)

        except Exception as e:
            print("❌ Error in new_notification:", str(e))
            await sio.emit("notification_count", {
                "error": str(e)
            }, to=sid)


@sio.on("notification_viewed")
async def notification_viewed(sid, data):
    notification_ids = data.get("notification_ids")
    user_id = data.get("user_id")

    if not notification_ids or not user_id:
        return await sio.emit("read_notifications", {
            "error": "Missing notification_ids or user_id"
        }, to=sid)

    async with async_session() as session:
        try:
            # Join IDs as comma-separated string for stored procedure
            unread_notifications_str = ",".join(notification_ids)

            # Execute the stored procedure
            await session.execute(_view_notifications, {"NotificationIds": unread_notifications_str})

            # Commit changes
            await session.commit()

            # Notify the recipient
            recipient_sid = userMap.get(user_id)
            if recipient_sid:
                await sio.emit("read_notifications", {
                    "read_notifications": notification_ids
                }, to=recipient_sid)

        except Exception as e:
            await session.rollback()
            await sio.emit("error_notifications", {
                "error": str(e)
            }, to=sid)
    

@sio.on("like_notification")
async def like_notification(sid, data):
    notification_id = data.get("notification_id")
    user_id = data.get("user_id")

    if not notification_id or not user_id:
        return await sio.emit("receive_like_notification", {
            "error": "Missing notification_id or user_id"
        }, to=sid)

    async with async_session() as session:
        try:
            result = await session.execute(
                text("""
                    SELECT u.username, n.message
                    FROM notifications n
                    JOIN users u ON n.actor = u.id
                    WHERE n.id = :notification_id
                """),
                {"notification_id": notification_id}
            )
            row = result.fetchone()
            if row:
                actor, message = row
                recipient_sid = userMap.get(user_id)
                if recipient_sid:
                    await sio.emit("receive_like_notification", {
                        "actor": actor,
                        "message": message
                    }, to=recipient_sid)
                else:
                    print(f"⚠️ User {user_id} not connected")
            else:
                await sio.emit("receive_like_notification", {
                    "error": "Notification not found"
                }, to=sid)
        except Exception as e:
            await sio.emit("receive_like_notification", {
                "error": str(e)
            }, to=sid)
