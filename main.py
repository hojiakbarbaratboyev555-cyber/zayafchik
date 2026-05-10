import logging
import sqlite3
import os
import random
import uvicorn

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Update
)

from fastapi import FastAPI, Request

# ================= CONFIG =================

API_TOKEN = "7941857519:AAEe0Ew4AKOmKi40JiBrxHXKg94bNZueVeg"

WEBHOOK_HOST = "https://zayafchik.onrender.com"

PORT = int(os.getenv("PORT", 10000))

WEBHOOK_PATH = f"/webhook/{API_TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

logging.basicConfig(level=logging.INFO)

bot = Bot(API_TOKEN)
dp = Dispatcher()

# ================= DATABASE =================

conn = sqlite3.connect("db.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER,
    channel_id TEXT,
    code TEXT
)
""")

conn.commit()

# ================= MENU =================

menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📦 Kanal ulash"),
            KeyboardButton(text="🔗 Qo‘shilish")
        ]
    ],
    resize_keyboard=True
)

# ================= STATES =================

state = {}

# ================= CODE GENERATOR =================

def generate_code():
    return str(random.randint(10000, 99999))

# ================= START =================

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "Kerakli bo‘limni tanlang 👇",
        reply_markup=menu
    )

# ================= KANAL ULASH =================

@dp.message(F.text == "📦 Kanal ulash")
async def connect_channel(message: types.Message):

    state[message.from_user.id] = "channel"

    await message.answer(
        "1️⃣ Botni kanalingizga admin qiling\n\n"
        "2️⃣ Invite link yaratish huquqini bering\n\n"
        "3️⃣ Kanal IDsini yuboring"
    )

# ================= CHANNEL ID =================

@dp.message(F.text, lambda message: state.get(message.from_user.id) == "channel")
async def save_channel(message: types.Message):

    try:
        chat_id = int(message.text)

        member = await bot.get_chat_member(chat_id, bot.id)

        if member.status not in ["administrator", "creator"]:

            await message.answer(
                "❌ Bot kanalda admin emas"
            )

            return

    except:

        await message.answer(
            "❌ Kanal ID noto‘g‘ri"
        )

        return

    code = generate_code()

    cur.execute(
        "INSERT INTO channels (owner_id, channel_id, code) VALUES (?, ?, ?)",
        (
            message.from_user.id,
            str(chat_id),
            code
        )
    )

    conn.commit()

    state.pop(message.from_user.id)

    await message.answer(
        f"✅ Kanal ulandi\n\n"
        f"🔑 Kod: {code}"
    )

# ================= JOIN =================

@dp.message(F.text == "🔗 Qo‘shilish")
async def join(message: types.Message):

    state[message.from_user.id] = "join"

    await message.answer(
        "🔑 5 xonali kodni yuboring"
    )

# ================= CODE CHECK =================

@dp.message(F.text, lambda message: state.get(message.from_user.id) == "join")
async def check_code(message: types.Message):

    code = message.text.strip()

    cur.execute(
        "SELECT * FROM channels WHERE code=?",
        (code,)
    )

    channel = cur.fetchone()

    if not channel:

        await message.answer(
            "❌ Kod topilmadi"
        )

        return

    try:

        invite = await bot.create_chat_invite_link(
            chat_id=channel[2],
            member_limit=1
        )

        await message.answer(
            f"🔗 Kanal havolasi:\n\n{invite.invite_link}"
        )

    except:

        await message.answer(
            "❌ Link yaratib bo‘lmadi"
        )

    state.pop(message.from_user.id)

# ================= BOT CHANNEL STATUS =================

@dp.my_chat_member()
async def bot_status(update: types.ChatMemberUpdated):

    chat = update.chat

    if chat.type not in ["channel", "supergroup"]:
        return

    new_status = update.new_chat_member.status

    if new_status not in ["administrator", "creator"]:

        cur.execute(
            "DELETE FROM channels WHERE channel_id=?",
            (str(chat.id),)
        )

        conn.commit()

# ================= FASTAPI =================

app = FastAPI()

@app.on_event("startup")
async def startup():

    await bot.set_webhook(WEBHOOK_URL)

@app.post(WEBHOOK_PATH)
async def webhook(request: Request):

    data = await request.json()

    update = Update.model_validate(data)

    await dp.feed_update(bot, update)

    return {"ok": True}

@app.get("/")
async def home():
    return {"status": "running"}

# ================= RUN =================

if __name__ == "__main__":

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT
)
