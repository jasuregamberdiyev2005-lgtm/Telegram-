import os
import base64
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from telegram import Bot

load_dotenv()

TOKEN = os.environ["8647124051:AAHlPDOpMohqUT2-F2lcAsEpCxub-mdlZgE"]
ADMIN_ID = int(os.environ["5203992395"])

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For tighter security, replace with your Netlify domain.
    allow_credentials=False,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)

bot = Bot(TOKEN)
UPLOADS = Path("uploads")
UPLOADS.mkdir(exist_ok=True)

class Photo(BaseModel):
    uid: int
    image: str

@app.get("/health")
async def health():
    return {"ok": True}

@app.post("/upload")
async def upload(photo: Photo):
    if photo.uid <= 0:
        raise HTTPException(400, "Invalid user id")

    try:
        header, encoded = photo.image.split(",", 1)
        if not header.startswith("data:image/"):
            raise ValueError
        raw = base64.b64decode(encoded)
    except Exception:
        raise HTTPException(400, "Invalid image")

    if not raw or len(raw) > 10 * 1024 * 1024:
        raise HTTPException(413, "Image too large")

    path = UPLOADS / f"{uuid.uuid4().hex}.jpg"
    path.write_bytes(raw)

    try:
        with path.open("rb") as f:
            await bot.send_photo(
                chat_id=photo.uid,
                photo=f,
                caption="Siz olgan surat."
            )

        with path.open("rb") as f:
            await bot.send_photo(
                chat_id=ADMIN_ID,
                photo=f,
                caption=f"Yangi surat | user_id: {photo.uid}"
            )
    finally:
        path.unlink(missing_ok=True)

    return {"ok": True}
