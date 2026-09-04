import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from contextlib import asynccontextmanager
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import engine, Base, get_db
from .socket_manager import manager
from .models import Church, Room, User
from .schemas import GuestJoinResponse
from .gemini_worker import GeminiWorker

# Active workers dictionary
active_gemini_workers: dict[str, GeminiWorker] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP: Create Database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    yield  # Application runs here
    
    # SHUTDOWN: Graceful database disposal
    await engine.dispose()

# Initialize FastAPI
app = FastAPI(lifespan=lifespan, title="Kizuna API")

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "Kizuna Backend"}

@app.websocket("/ws/listen/{room_id}/{language}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, language: str):
    await manager.connect(websocket, room_id, language)
    try:
        while True:
            # Keep-alive loop for listener clients
            data = await websocket.receive_text()
            await manager.broadcast_to_language(f"Echo: {data}", room_id, language)
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id, language)

@app.websocket("/ws/stream/{room_id}")
async def stream_audio(websocket: WebSocket, room_id: str):
    """
    Endpoint for Church Admin / Preacher.
    Receives raw PCM audio bytes from microphone and feeds GeminiWorker.
    """
    await websocket.accept()
    loop = asyncio.get_running_loop()
    
    worker = GeminiWorker(room_id, loop)
    worker.start()
    active_gemini_workers[room_id] = worker
    
    try:
        while True:
            audio_chunk = await websocket.receive_bytes()
            worker.process_audio_chunk(audio_chunk)
    except WebSocketDisconnect:
        print(f"Preacher disconnected from room {room_id}")
    finally:
        worker.stop()
        if room_id in active_gemini_workers:
            del active_gemini_workers[room_id]

@app.post("/api/join/{qr_code_hash}", response_model=GuestJoinResponse)
async def silent_guest_login(qr_code_hash: str, db: AsyncSession = Depends(get_db)):
    query = select(Church).where(Church.qr_code_hash == qr_code_hash)
    result = await db.execute(query)
    church = result.scalar_one_or_none()

    if not church:
        raise HTTPException(status_code=404, detail="Invalid QR code. Church not found.")

    room_query = select(Room).where(Room.church_id == church.id, Room.is_live == True)
    room_result = await db.execute(room_query)
    active_room = room_result.scalar_one_or_none()

    is_live = active_room is not None
    room_id = active_room.id if active_room else None

    new_guest = User(is_guest=True)
    db.add(new_guest)
    await db.commit()
    await db.refresh(new_guest)

    return GuestJoinResponse(
        status="success",
        user_id=new_guest.id,
        church_name=church.name,
        is_live=is_live,
        room_id=room_id
    )

@app.post("/api/dev/seed")
async def seed_test_data(db: AsyncSession = Depends(get_db)):
    church = Church(name="Kizuna Test Church", qr_code_hash="test-hash-123")
    db.add(church)
    await db.commit()
    await db.refresh(church)
    
    room = Room(church_id=church.id, is_live=True)
    db.add(room)
    await db.commit()
    
    return {"message": "Test church and live room created!", "qr_hash": church.qr_code_hash}