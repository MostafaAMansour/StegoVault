from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from jose import JWTError, jwt
from PIL import Image
import numpy as np
import bcrypt
import io
import os
import json
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "stegoapp-super-secret-change-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 day

DATABASE_URL = "sqlite+aiosqlite:///./stegoapp.db"
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)

app = FastAPI(title="StegoApp API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

# ── DB Models ─────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    username: Mapped[str] = mapped_column(String, primary_key=True)
    password_hash: Mapped[str] = mapped_column(String)          # bcrypt of text pw
    image_hash: Mapped[str] = mapped_column(String)             # hash of image pixels

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    async with async_session() as session:
        yield session

# ── Steganography core (LSB) ───────────────────────────────────────────────────
DELIMITER = "<<<END>>>"

def _img_capacity(img: Image.Image) -> int:
    """Max chars we can hide (3 bits per pixel / 8 bits per char)."""
    arr = np.array(img)
    return (arr.size * 3) // 8  # rough: use 3 colour channels, 1 bit each

def encode_message(image_bytes: bytes, message: str) -> bytes:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    arr = np.array(img, dtype=np.uint8)

    full_msg = message + DELIMITER
    bits = "".join(format(ord(c), "08b") for c in full_msg)

    capacity = arr.size  # total values across R,G,B channels
    if len(bits) > capacity:
        raise ValueError("Message too long for this image.")

    flat = arr.flatten().copy()
    for i, bit in enumerate(bits):
        flat[i] = (flat[i] & 0xFE) | int(bit)

    result = flat.reshape(arr.shape)
    out = io.BytesIO()
    Image.fromarray(result.astype(np.uint8)).save(out, format="PNG")
    out.seek(0)
    return out.read()

def decode_message(image_bytes: bytes) -> str:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    flat = np.array(img, dtype=np.uint8).flatten()

    bits = [str(v & 1) for v in flat]
    chars, msg = [], ""
    for i in range(0, len(bits) - 7, 8):
        byte = "".join(bits[i : i + 8])
        ch = chr(int(byte, 2))
        msg += ch
        if msg.endswith(DELIMITER):
            return msg[: -len(DELIMITER)]
    raise ValueError("No hidden message found.")

# ── Auth helpers ──────────────────────────────────────────────────────────────
def hash_image(image_bytes: bytes) -> str:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((64, 64))
    return hashlib.sha256(np.array(img).tobytes()).hexdigest()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# ── Routes ────────────────────────────────────────────────────────────────────

# ---------- Auth ----------
@app.post("/auth/signup")
async def signup(
    username: str = Form(...),
    password: str = Form(...),
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.username == username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already taken")

    image_bytes = await image.read()
    image_hash = hash_image(image_bytes)
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    user = User(username=username, password_hash=pw_hash, image_hash=image_hash)
    db.add(user)
    await db.commit()
    return {"message": "Account created successfully"}

@app.post("/auth/login")
async def login(
    username: str = Form(...),
    password: str = Form(...),
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    image_bytes = await image.read()
    if hash_image(image_bytes) != user.image_hash:
        raise HTTPException(status_code=401, detail="Image password does not match")

    token = create_access_token({"sub": user.username}, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return {"access_token": token, "token_type": "bearer", "username": user.username}

@app.get("/auth/me")
async def me(current_user: User = Depends(get_current_user)):
    return {"username": current_user.username}

# ---------- Steganography ----------
@app.post("/stego/encode")
async def encode(
    image: UploadFile = File(...),
    message: str = Form(...),
):
    image_bytes = await image.read()
    try:
        result_bytes = encode_message(image_bytes, message)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return StreamingResponse(
        io.BytesIO(result_bytes),
        media_type="image/png",
        headers={"Content-Disposition": "attachment; filename=encoded.png"},
    )

@app.post("/stego/decode")
async def decode(
    image: UploadFile = File(...),
):
    image_bytes = await image.read()
    try:
        message = decode_message(image_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": message}

@app.get("/health")
async def health():
    return {"status": "ok"}
