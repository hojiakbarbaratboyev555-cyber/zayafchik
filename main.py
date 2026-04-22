import logging
import sqlite3
import os

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, Update
from aiogram.utils import executor

from flask import Flask, request

API_TOKEN = "7941857519:AAFvwtO6F1HPRBPnkss3JpyWw9leKSKsTJE"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

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
menu = ReplyKeyboardMarkup(resize_keyboard=True)
menu.add("📦 Buyurtma berish", "🔗 Qo‘shilish")

state = {}

# ================= START =================
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer("Kerakli bo‘limni tanlang:", reply_markup=menu)

# ================= BUYURTMA =================
@dp.message_handler(lambda m: m.text == "📦 Buyurtma berish")
async def order(message: types.Message):
    state[message.from_user.id] = "waiting_channel"
    await message.answer(
        "Botni o‘z kanalingizga qo‘shing va ADMIN qiling.\n"
        "So‘ng kanal username yoki link yuboring:"
    )

# ================= CHANNEL SAVE =================
@dp.message_handler(lambda m: state.get(m.from_user.id) == "waiting_channel")
async def save_channel(message: types.Message):
    channel = message.text

    try:
        member = await bot.get_chat_member(channel, bot.id)
        if member.status not in ["administrator", "creator"]:
            await message.answer("❌ Bot admin emas!")
            return
    except:
        await message.answer("❌ Kanal topilmadi!")
        return

    cursor.execute("INSERT INTO channels (channel) VALUES (?)", (channel,))
    conn.commit()

    order_id = cursor.lastrowid
    state[message.from_user.id] = None

    await message.answer(
        f"✅ Buyurtma qabul qilindi!\nSizning ID: {order_id}",
        reply_markup=menu
    )

# ================= JOIN =================
@dp.message_handler(lambda m: m.text == "🔗 Qo‘shilish")
async def join(message: types.Message):
    state[message.from_user.id] = "waiting_id"
    await message.answer("ID kiriting:")

# ================= SEND LINK =================
@dp.message_handler(lambda m: state.get(m.from_user.id) == "waiting_id")
async def send_link(message: types.Message):
    try:
        order_id = int(message.text)
    except:
        await message.answer("❌ Noto‘g‘ri ID")
        return

    cursor.execute("SELECT channel FROM channels WHERE id=?", (order_id,))
    result = cursor.fetchone()

    if not result:
        await message.answer("❌ Bunday ID mavjud emas")
        return

    cursor.execute(
        "SELECT * FROM used WHERE user_id=? AND order_id=?",
        (message.from_user.id, order_id)
    )

    if cursor.fetchone():
        await message.answer("❌ Siz bu ID dan allaqachon foydalangansiz")
        return

    channel = result[0]

    cursor.execute(
        "INSERT INTO used (user_id, order_id) VALUES (?, ?)",
        (message.from_user.id, order_id)
    )
    conn.commit()

    invite = await bot.create_chat_invite_link(
        chat_id=channel,
        creates_join_request=True
    )

    await message.answer(f"Qo‘shilish uchun link:\n{invite.invite_link}")

# ================= AUTO APPROVE =================
@dp.chat_join_request_handler()
async def approve_user(join_request: types.ChatJoinRequest):
    await bot.approve_chat_join_request(
        chat_id=join_request.chat.id,
        user_id=join_request.from_user.id
    )

# ================= FLASK =================
app = Flask(__name__)

WEBHOOK_PATH = f"/webhook/{API_TOKEN}"
WEBHOOK_URL = os.getenv("https://zayafchik.onrender.com") + WEBHOOK_PATH

@app.route(WEBHOOK_PATH, methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dp.process_update(update)
    return "ok"

@app.route("/")
def index():
    return "Bot ishlayapti"

# ================= START =================
if __name__ == "__main__":
    import asyncio

    async def on_startup(dp):
        await bot.set_webhook(WEBHOOK_URL)

    executor.start_webhook(
        dispatcher=dp,
        webhook_path=WEBHOOK_PATH,
        on_startup=on_startup,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
    )
