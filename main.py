import logging
import sqlite3
import os
import uvicorn

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums import ChatMemberStatus

from fastapi import FastAPI, Request

# ================= CONFIG =================
API_TOKEN = "7941857519:AAGn5A6YqPx57Swa_RB3xjJaOqrG9kOijX4"
WEBHOOK_HOST = "https://zayafchik.onrender.com"

PORT = int(os.getenv("PORT", 10000))

WEBHOOK_PATH = f"/webhook/{API_TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

logging.basicConfig(level=logging.INFO)

# ================= BOT =================
bot = Bot(API_TOKEN)
dp = Dispatcher()

# ================= DATABASE =================
conn = sqlite3.connect("database.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS used (
    user_id INTEGER,
    order_id INTEGER
)
""")

conn.commit()

# ================= KEYBOARDS =================

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📦 Buyurtma berish")],
        [KeyboardButton(text="🔗 Qo‘shilish")]
    ],
    resize_keyboard=True
)

buyurtma_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📢 Kanalga qo‘shish")],
        [KeyboardButton(text="♻️ Tekshirish")],
        [KeyboardButton(text="⬅️ Orqaga")]
    ],
    resize_keyboard=True
)

state = {}

# ================= START =================
@dp.message(Command("start"))
async def start(m: types.Message):
    await m.answer("Asosiy menu:", reply_markup=main_menu)

# ================= BUYURTMA =================
@dp.message(lambda m: m.text == "📦 Buyurtma berish")
async def buyurtma(m: types.Message):
    await m.answer("Buyurtma bo‘limi:", reply_markup=buyurtma_menu)

# ================= ORQAGA =================
@dp.message(lambda m: m.text == "⬅️ Orqaga")
async def back(m: types.Message):
    await m.answer("Asosiy menu:", reply_markup=main_menu)

# ================= ADD CHANNEL =================
@dp.message(lambda m: m.text == "📢 Kanalga qo‘shish")
async def add_channel(m: types.Message):
    chat_id = m.chat.id

    try:
        member = await bot.get_chat_member(chat_id, bot.id)

        if member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
            await m.answer("❌ Bot admin emas! Avval admin qiling.")
            return

    except:
        await m.answer("❌ Kanal yoki guruh topilmadi!")
        return

    cur.execute("INSERT INTO channels (chat_id) VALUES (?)", (chat_id,))
    conn.commit()

    await m.answer("✅ Kanal/Guruh saqlandi!")

# ================= CHECK =================
@dp.message(lambda m: m.text == "♻️ Tekshirish")
async def check(m: types.Message):
    cur.execute("SELECT chat_id FROM channels")
    rows = cur.fetchall()

    if not rows:
        await m.answer("❌ Hech narsa yo‘q")
        return

    text = "📋 RO‘YXAT:\n\n"

    for r in rows:
        chat_id = r[0]

        try:
            member = await bot.get_chat_member(chat_id, bot.id)

            if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                text += f"✅ {chat_id} — OK\n"
            else:
                text += f"❌ {chat_id} — admin emas\n"

        except:
            text += f"⚠️ {chat_id} — xato\n"

    await m.answer(text)

# ================= FASTAPI =================
app = FastAPI()

@app.on_event("startup")
async def startup():
    await bot.set_webhook(WEBHOOK_URL)

@app.post(WEBHOOK_PATH)
async def webhook(request: Request):
    data = await request.json()
    update = types.Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}

@app.get("/")
async def home():
    return {"status": "bot ishlayapti"}

# ================= RUN =================
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
