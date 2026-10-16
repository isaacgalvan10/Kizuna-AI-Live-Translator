import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from contextlib import asynccontextmanager
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import create_operator_token, get_operator_claims, hash_password, verify_password
from .database import engine, Base, get_db
from .socket_manager import manager
from .models import Church, Room, User
from .schemas import (
    GuestJoinResponse,
    OperatorLoginRequest,
    OperatorLoginResponse,
    OperatorProfileResponse,
)
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

@app.post("/api/operator/login", response_model=OperatorLoginResponse)
async def operator_login(payload: OperatorLoginRequest, db: AsyncSession = Depends(get_db)):
    query = select(User).where(User.email == payload.email, User.is_guest == False)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if user is None or user.church_id is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return OperatorLoginResponse(
        access_token=create_operator_token(user.email, user.church_id),
        token_type="bearer",
        church_id=user.church_id,
    )

@app.get("/api/operator/me", response_model=OperatorProfileResponse)
async def operator_profile(claims: dict = Depends(get_operator_claims)):
    return OperatorProfileResponse(email=claims["sub"], church_id=int(claims["church_id"]))

TEST_CHURCH_QR_HASH = "test-hash-123"
TEST_OPERATOR_EMAIL = "operator@kizuna.test"
TEST_OPERATOR_PASSWORD = "kizuna-operator-test"

@app.post("/api/dev/seed")
async def seed_test_data(db: AsyncSession = Depends(get_db)):
    church_query = select(Church).where(Church.qr_code_hash == TEST_CHURCH_QR_HASH)
    church = (await db.execute(church_query)).scalar_one_or_none()
    if church is None:
        church = Church(name="Kizuna Test Church", qr_code_hash=TEST_CHURCH_QR_HASH)
        db.add(church)
        await db.commit()
        await db.refresh(church)

    room_query = select(Room).where(Room.church_id == church.id)
    if (await db.execute(room_query)).scalar_one_or_none() is None:
        db.add(Room(church_id=church.id, is_live=True))

    operator_query = select(User).where(User.email == TEST_OPERATOR_EMAIL)
    operator = (await db.execute(operator_query)).scalar_one_or_none()
    if operator is None:
        operator = User(email=TEST_OPERATOR_EMAIL)
        db.add(operator)
    operator.is_guest = False
    operator.church_id = church.id
    operator.hashed_password = hash_password(TEST_OPERATOR_PASSWORD)

    await db.commit()

    return {
        "message": "Test church, live room, and operator ready!",
        "qr_hash": church.qr_code_hash,
        "church_id": church.id,
        "operator_email": TEST_OPERATOR_EMAIL,
        "operator_password": TEST_OPERATOR_PASSWORD,
    }