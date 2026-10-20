import asyncio
import logging
import os

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    WebSocketException,
    status,
)
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import update
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import (
    create_operator_token,
    get_current_operator,
    get_operator_claims,
    hash_password,
    operator_claims_from_token,
    verify_password,
)
from .church_glossary import ChurchGlossaryError, load_church_glossary
from .database import engine, Base, get_db
from .socket_manager import (
    FEED_STATE_LIVE,
    FEED_STATE_PAUSED,
    FEED_STATE_STOPPED,
    FeedState,
    manager,
)
from .models import Church, Room, User, new_qr_hash
from .schemas import (
    FeedControlResponse,
    GuestJoinResponse,
    OperatorChurchResponse,
    OperatorLoginRequest,
    OperatorLoginResponse,
    OperatorProfileResponse,
    RoomSummary,
)
from .gemini_worker import GeminiWorker

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger(__name__)

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

# The React dev server runs on its own origin (5173), so the browser requires
# the API to opt in to cross-origin calls. Only the local dev origins are allowed;
# tighten this when a real deployment origin exists.
DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=DEV_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
async def stream_audio(
    websocket: WebSocket,
    room_id: int,
    token: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Audio intake for the operator console.
    Requires an operator JWT (as a query parameter — browsers cannot attach
    headers to a WebSocket handshake) for the church that owns the room.
    Receives raw PCM audio bytes from the mixer feed and feeds GeminiWorker.
    """
    claims = operator_claims_from_token(token)
    if claims is None:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)

    room_query = select(Room).where(
        Room.id == room_id, Room.church_id == int(claims["church_id"])
    )
    room = (await db.execute(room_query)).scalar_one_or_none()
    if room is None:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)

    # A church without a glossary gets the default terminology. A stored
    # glossary that fails validation aborts the handshake instead of being
    # silently ignored: a clear failure is safer than wrong translations.
    try:
        glossary = await load_church_glossary(db, room.church_id)
    except ChurchGlossaryError as exc:
        # Log only the location, never the validation message: parser errors
        # can quote glossary content (names and terms are personal data).
        logger.error(
            "church_glossary_invalid room_id=%d church_id=%d",
            room.id,
            room.church_id,
        )
        raise WebSocketException(
            code=status.WS_1011_INTERNAL_ERROR,
            reason="Church Glossary is invalid. Contact an administrator.",
        ) from exc

    await websocket.accept()
    loop = asyncio.get_running_loop()

    worker = GeminiWorker(str(room.id), loop, glossary=glossary)
    worker.start()
    active_gemini_workers[str(room.id)] = worker

    try:
        while True:
            audio_chunk = await websocket.receive_bytes()
            worker.process_audio_chunk(audio_chunk)
    except WebSocketDisconnect:
        print(f"Operator disconnected from room {room_id}")
    finally:
        worker.stop()
        if str(room.id) in active_gemini_workers:
            del active_gemini_workers[str(room.id)]

@app.post("/api/join/{qr_code_hash}", response_model=GuestJoinResponse)
async def silent_guest_login(qr_code_hash: str, db: AsyncSession = Depends(get_db)):
    query = select(Church).where(Church.qr_code_hash == qr_code_hash)
    result = await db.execute(query)
    church = result.scalar_one_or_none()

    if not church:
        raise HTTPException(status_code=404, detail="Invalid QR code. Church not found.")

    # A scanned code resolves to the church's live room when one is running and
    # to its first room otherwise, so a guest can already wait before the feed
    # starts. room_id is only null when the church has no room at all.
    room = (
        await db.execute(
            select(Room)
            .where(Room.church_id == church.id)
            .order_by(Room.is_live.desc(), Room.id)
            .limit(1)
        )
    ).scalars().first()

    new_guest = User(is_guest=True)
    db.add(new_guest)
    await db.commit()
    await db.refresh(new_guest)

    return GuestJoinResponse(
        status="success",
        user_id=new_guest.id,
        church_name=church.name,
        is_live=bool(room and room.is_live),
        room_id=room.id if room else None
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

@app.get("/api/operator/church", response_model=OperatorChurchResponse)
async def operator_church(
    church_id: int = Depends(get_current_operator),
    db: AsyncSession = Depends(get_db),
):
    church = (
        await db.execute(select(Church).where(Church.id == church_id))
    ).scalar_one_or_none()
    if church is None:
        raise HTTPException(status_code=404, detail="Church not found")

    # The QR hash is the church's permanent identity: generated once, never
    # tied to the operator login, so printed codes survive password rotations.
    # The conditional UPDATE keeps concurrent first loads from minting two
    # different hashes for the same church.
    if church.qr_code_hash is None:
        await db.execute(
            update(Church)
            .where(Church.id == church.id, Church.qr_code_hash.is_(None))
            .values(qr_code_hash=new_qr_hash())
        )
        await db.commit()
        await db.refresh(church)

    rooms = (
        await db.execute(select(Room).where(Room.church_id == church_id).order_by(Room.id))
    ).scalars().all()

    return OperatorChurchResponse(
        id=church.id,
        name=church.name,
        qr_code_hash=church.qr_code_hash,
        rooms=[RoomSummary(id=room.id, is_live=room.is_live) for room in rooms],
    )

async def _apply_feed_control(
    room_id: int,
    church_id: int,
    state: FeedState,
    db: AsyncSession,
    is_live: bool | None = None,
) -> FeedControlResponse:
    query = select(Room).where(Room.id == room_id, Room.church_id == church_id)
    room = (await db.execute(query)).scalar_one_or_none()
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    if is_live is not None:
        room.is_live = is_live
        await db.commit()

    await manager.broadcast_feed_state(str(room.id), state)

    return FeedControlResponse(status=state)

@app.post("/api/operator/rooms/{room_id}/start", response_model=FeedControlResponse)
async def start_live_feed(
    room_id: int,
    church_id: int = Depends(get_current_operator),
    db: AsyncSession = Depends(get_db),
):
    return await _apply_feed_control(room_id, church_id, FEED_STATE_LIVE, db, is_live=True)

@app.post("/api/operator/rooms/{room_id}/pause", response_model=FeedControlResponse)
async def pause_live_feed(
    room_id: int,
    church_id: int = Depends(get_current_operator),
    db: AsyncSession = Depends(get_db),
):
    return await _apply_feed_control(room_id, church_id, FEED_STATE_PAUSED, db)

@app.post("/api/operator/rooms/{room_id}/stop", response_model=FeedControlResponse)
async def stop_live_feed(
    room_id: int,
    church_id: int = Depends(get_current_operator),
    db: AsyncSession = Depends(get_db),
):
    return await _apply_feed_control(room_id, church_id, FEED_STATE_STOPPED, db, is_live=False)

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