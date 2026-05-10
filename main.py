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

API_TOKEN = os.getenv("7941857519:AAHlGNrQzK5uZjeFeYQIXykC9VEgPK9B4MU")

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

# ================= STATE =================

state = {}

# ================= CODE =================

def generate_code():
    return str(random.randint(10000, 99999))

# ================= START =================

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Kerakli bo‘limni tanlang 👇", reply_markup=menu)

# ================= INLINE MENU =================

@dp.message(F.text == "📦 Kanal ulash")
async def connect_channel(message: types.Message):

    bot_username = (await bot.get_me()).username

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Kanal ulash",
                    url=f"https://t.me/{bot_username}?startchannel=new&admin=invite_users"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👥 Guruh ulash",
                    url=f"https://t.me/{bot_username}?startgroup=new&admin=invite_users"
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Tasdiqlash",
                    callback_data="verify_admin"
                )
            ]
        ]
    )

    await message.answer(
        "Kerakli amalni tanlang 👇",
        reply_markup=kb
    )

# ================= BOT STATUS (NEW FIX) =================

@dp.my_chat_member()
async def bot_status(update: types.ChatMemberUpdated):

    chat = update.chat

    if chat.type not in ["channel", "supergroup"]:
        return

    new_status = update.new_chat_member.status

    # BOT ADMIN BO‘LIB QO‘SHILDI
    if new_status in ["administrator", "creator"]:

        cur.execute(
            "INSERT INTO channels (owner_id, channel_id, code) VALUES (?, ?, '')",
            (update.from_user.id, str(chat.id))
        )
        conn.commit()

    # ❌ BOT CHIQARILDI → HAMMASI O‘CHADI
    elif new_status in ["kicked", "left"]:

        cur.execute(
            "DELETE FROM channels WHERE channel_id=?",
            (str(chat.id),)
        )
        conn.commit()

# ================= VERIFY BOT ADMIN =================

@dp.callback_query(F.data == "verify_admin")
async def verify_admin(callback: types.CallbackQuery):

    user_id = callback.from_user.id

    cur.execute(
        "SELECT channel_id FROM channels WHERE owner_id=? AND code=''",
        (user_id,)
    )

    data = cur.fetchone()

    if not data:
        return await callback.message.answer("❌ Kanal/guruh topilmadi")

    chat_id = data[0]

    try:
        bot_member = await bot.get_chat_member(chat_id, bot.id)

        if bot_member.status not in ["administrator", "creator"]:
            return await callback.message.answer("❌ Bot bu kanal/guruhda admin emas")

    except:
        return await callback.message.answer("❌ Tekshirishda xatolik")

    code = generate_code()

    cur.execute(
        "UPDATE channels SET code=? WHERE channel_id=?",
        (code, chat_id)
    )

    conn.commit()

    await callback.message.answer(f"✅ Tasdiqlandi!\n🔑 Kod: {code}")

    await callback.answer()

# ================= JOIN SYSTEM =================

@dp.message(F.text == "🔗 Qo‘shilish")
async def join(message: types.Message):

    state[message.from_user.id] = "join"
    await message.answer("🔑 5 xonali kodni yuboring")

@dp.message(F.text)
async def check_code(message: types.Message):

    if state.get(message.from_user.id) != "join":
        return

    code = message.text.strip()

    cur.execute(
        "SELECT channel_id FROM channels WHERE code=?",
        (code,)
    )

    channel = cur.fetchone()

    if not channel:
        return await message.answer("❌ Kod topilmadi")

    try:
        invite = await bot.create_chat_invite_link(
            chat_id=channel[0],
            member_limit=1   # 🔥 1 MARTALIK LINK
        )

        await message.answer(f"🔗 Kanal havolasi:\n{invite.invite_link}")

    except:
        await message.answer("❌ Link yaratib bo‘lmadi")

    state.pop(message.from_user.id)

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
    uvicorn.run(app, host="0.0.0.0", port=PORT)
