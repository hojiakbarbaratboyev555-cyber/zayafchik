import logging
import sqlite3

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, Update
from aiogram.enums import ChatMemberStatus

from fastapi import FastAPI, Request
import uvicorn
import os

API_TOKEN = "7941857519:AAGn5A6YqPx57Swa_RB3xjJaOqrG9kOijX4"
WEBHOOK_HOST = "https://zayafchik.onrender.com"

PORT = int(os.getenv("PORT", 10000))

WEBHOOK_PATH = f"/webhook/{API_TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# ================= DATABASE =================
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS used (
    user_id INTEGER,
    order_id INTEGER
)
""")

conn.commit()

# ================= BUTTONS =================
menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📦 Buyurtma berish"), KeyboardButton(text="🔗 Qo‘shilish")]
    ],
    resize_keyboard=True
)

state = {}

# ================= HANDLERS =================
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Kerakli bo‘limni tanlang:", reply_markup=menu)

@dp.message(lambda m: m.text == "📦 Buyurtma berish")
async def order(message: types.Message):
    state[message.from_user.id] = "waiting_channel"
    await message.answer("Kanal username yuboring:")

@dp.message(lambda m: state.get(m.from_user.id) == "waiting_channel")
async def save_channel(message: types.Message):
    channel = message.text

    try:
        member = await bot.get_chat_member(channel, bot.id)
        if member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
            await message.answer("❌ Bot admin emas!")
            return
    except:
        await message.answer("❌ Kanal topilmadi!")
        return

    cursor.execute("INSERT INTO channels (channel) VALUES (?)", (channel,))
    conn.commit()

    order_id = cursor.lastrowid
    state[message.from_user.id] = None

    await message.answer(f"✅ ID: {order_id}")

@dp.message(lambda m: m.text == "🔗 Qo‘shilish")
async def join(message: types.Message):
    state[message.from_user.id] = "waiting_id"
    await message.answer("ID kiriting:")

@dp.message(lambda m: state.get(m.from_user.id) == "waiting_id")
async def send_link(message: types.Message):
    try:
        order_id = int(message.text)
    except:
        await message.answer("❌ Noto‘g‘ri ID")
        return

    cursor.execute("SELECT channel FROM channels WHERE id=?", (order_id,))
    result = cursor.fetchone()

    if not result:
        await message.answer("❌ Topilmadi")
        return

    channel = result[0]

    cursor.execute("SELECT * FROM used WHERE user_id=? AND order_id=?", (message.from_user.id, order_id))
    if cursor.fetchone():
        await message.answer("❌ Allaqachon ishlatilgan")
        return

    cursor.execute("INSERT INTO used (user_id, order_id) VALUES (?, ?)", (message.from_user.id, order_id))
    conn.commit()

    invite = await bot.create_chat_invite_link(
        chat_id=channel,
        creates_join_request=True
    )

    await message.answer(invite.invite_link)

# ================= AUTO APPROVE =================
@dp.chat_join_request()
async def approve(event: types.ChatJoinRequest):
    await bot.approve_chat_join_request(
        chat_id=event.chat.id,
        user_id=event.from_user.id
    )

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

# ================= RUN SERVER =================
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
