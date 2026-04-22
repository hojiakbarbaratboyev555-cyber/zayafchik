import logging
import sqlite3
import os
import uvicorn

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, Update
from aiogram.enums import ChatMemberStatus

from fastapi import FastAPI, Request

# ================= CONFIG =================
API_TOKEN = "7941857519:AAGWmFKQoI0MjxWhskB_Th2dDsaTf6d41v4"
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

# ================= KEYBOARD =================
menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📦 Buyurtma berish"), KeyboardButton(text="🔗 Qo‘shilish")]
    ],
    resize_keyboard=True
)

state = {}

# ================= START =================
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Kerakli bo‘limni tanlang:", reply_markup=menu)

# ================= BUYURTMA =================
@dp.message(F.text == "📦 Buyurtma berish")
async def order(message: types.Message):
    state[message.from_user.id] = "waiting_channel"

    await message.answer(
        "📌 Botni o‘z yopiq kanal yoki guruhingizga ADMIN qiling.\n\n"
        "So‘ng kanal ID sini yuboring:\n"
        "Masalan: -1001234567890"
    )

# ================= SAVE CHANNEL =================
@dp.message(F.text, lambda m: state.get(m.from_user.id) == "waiting_channel")
async def save_channel(message: types.Message):
    try:
        chat_id = int(message.text.strip())
    except:
        await message.answer("❌ Noto‘g‘ri ID!")
        return

    try:
        member = await bot.get_chat_member(chat_id, bot.id)

        if member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
            await message.answer("❌ Bot admin emas!")
            return

    except:
        await message.answer("❌ Kanal topilmadi!")
        return

    cursor.execute("INSERT INTO channels (channel) VALUES (?)", (str(chat_id),))
    conn.commit()

    order_id = cursor.lastrowid
    state.pop(message.from_user.id, None)

    await message.answer(f"✅ Saqlandi!\n🆔 ID: {order_id}")

# ================= QO‘SHILISH (ONE-TIME LINK) =================
@dp.message(F.text == "🔗 Qo‘shilish")
async def join(message: types.Message):
    state[message.from_user.id] = "waiting_id"
    await message.answer("ID kiriting:")

@dp.message(F.text, lambda m: state.get(m.from_user.id) == "waiting_id")
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

    # oldin ishlatilganmi
    cursor.execute(
        "SELECT * FROM used WHERE user_id=? AND order_id=?",
        (message.from_user.id, order_id)
    )

    if cursor.fetchone():
        await message.answer("❌ Siz allaqachon ishlatgansiz")
        return

    cursor.execute(
        "INSERT INTO used (user_id, order_id) VALUES (?, ?)",
        (message.from_user.id, order_id)
    )
    conn.commit()

    # 🔥 ONE-TIME INVITE LINK
    invite = await bot.create_chat_invite_link(
        chat_id=channel,
        member_limit=1,  # 👈 FAAT 1 KISHI UCHUN
        creates_join_request=False
    )

    await message.answer(f"🔗 Sizning link:\n{invite.invite_link}")

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

# ================= RUN =================
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
