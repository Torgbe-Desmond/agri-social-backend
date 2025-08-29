import socketio

sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=["http://localhost:3000","https://agri-social.vercel.app"]
)

socket_app = socketio.ASGIApp(sio)  
userMap = {} 

def getSocket(user_id):
    print(userMap)
    return userMap.get(user_id)

@sio.event
async def connect(sid, environ):
    print(f"🔌 Connected: {sid}")

@sio.event
async def disconnect(sid):
    print(f"❌ Disconnected: {sid}")
    for uid, stored_sid in list(userMap.items()):
        if stored_sid == sid:
            del userMap[uid]
            print(f"🗑️ Removed {uid} from userMap")
            break
        
    await sio.leave_room(sid, "post_footer_notifications")
    print(f"🚪 {sid} left 'post_footer_notifications'")

@sio.event
async def chat_message(sid, data):
    print(f"💬 Message from {sid}: {data}")
    await sio.emit("chat_response", {"message": data}, to=sid)

@sio.on("user")
async def user_connection(sid, data):
    user_id = data.get("user_id")
    group = data.get("room") 

    if user_id:
        userMap[user_id] = sid
        print("📌 Current userMap:", userMap)

        if group:
            await sio.enter_room(sid, group)
            print(f"✅ {user_id} joined group '{group}'")





