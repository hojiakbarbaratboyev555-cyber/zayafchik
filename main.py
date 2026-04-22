import logging
import sqlite3
import os
import random
import string
import uvicorn

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, Update
)
from aiogram.enums import ChatMemberStatus

from fastapi import FastAPI, Request

# ================= CONFIG =================
API_TOKEN = "7941857519:AAGrOiq9YFTm6MrebIJBbSGEGS3_CNgdMjM"
WEBHOOK_HOST = "https://zayafchik.onrender.com"

ADMIN_GROUP_ID = -1003881398546
CARD_NUMBER = "9860196619854934"

PORT = int(os.getenv("PORT", 10000))
WEBHOOK_PATH = f"/webhook/{API_TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

logging.basicConfig(level=logging.INFO)

bot = Bot(API_TOKEN)
dp = Dispatcher()

# ================= DB =================
conn = sqlite3.connect("db.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER,
    channel_id TEXT,
    price TEXT,
    card TEXT,
    code TEXT
)
""")

conn.commit()

# ================= MENU =================
menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📦 Buyurtma berish"), KeyboardButton(text="🔗 Qo‘shilish")]
    ],
    resize_keyboard=True
)

state = {}
temp = {}

# ================= CODE =================
def generate_code():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=4))

# ================= START =================
@dp.message(Command("start"))
async def start(m: types.Message):
    await m.answer("Tanlang:", reply_markup=menu)

# ================= BUYURTMA =================
@dp.message(F.text == "📦 Buyurtma berish")
async def order(m: types.Message):
    state[m.from_user.id] = "pay"
    await m.answer(f"Buyurtma berish 📦\n💰 Narx: 10000 so‘m\n💳Karta: {CARD_NUMBER}\n\n⚠️Toʻlovni qilgandan soʻng chekni yuboring")

# ================= CHECK =================
@dp.message(F.photo, lambda m: state.get(m.from_user.id) == "pay")
async def check(m: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅", callback_data=f"approvepay_{m.from_user.id}")],
        [InlineKeyboardButton(text="❌", callback_data=f"rejectpay_{m.from_user.id}")]
    ])

    await bot.send_photo(
        ADMIN_GROUP_ID,
        m.photo[-1].file_id,
        caption=f"💰 TO‘LOV\nUser: {m.from_user.id}",
        reply_markup=kb
    )

    await m.answer("✅Chek qabul qilindi\n⏳ Adminlar tasdiqlashini kuting...")
    state[m.from_user.id] = "wait_admin"

# ================= ADMIN APPROVE =================
@dp.callback_query(F.data.startswith("approvepay_"))
async def approve_pay(c: types.CallbackQuery):
    user_id = int(c.data.split("_")[1])
    state[user_id] = "channel"

    await bot.send_message(user_id, "✅ Toʻlov Tasdiqlandi!\n\n🔻Botni kanalingizga admin qiling (❗Taklif havolalarini boshqarish imkoniyati boʻlsa yetadi)\n🔻Shu kanalingizning IDsini yuboring")
    await c.message.edit_caption("✅ ID tasdiqlandi")

# ================= ADMIN REJECT =================
@dp.callback_query(F.data.startswith("rejectpay_"))
async def reject_pay(c: types.CallbackQuery):
    user_id = int(c.data.split("_")[1])
    await bot.send_message(user_id, "❌ To‘lov bekor qilindi")
    await c.message.edit_caption("❌")

# ================= CHANNEL =================
@dp.message(F.text, lambda m: state.get(m.from_user.id) == "channel")
async def channel(m: types.Message):
    try:
        chat_id = int(m.text)
        member = await bot.get_chat_member(chat_id, bot.id)

        if member.status not in ["administrator", "creator"]:
            await m.answer("❌ Botga kanalingizda yetarlicha huquq berilmagan")
            return
    except:
        await m.answer("❌ ID notoʻgʻri kiritildi")
        return

    temp[m.from_user.id] = {"channel": chat_id}
    state[m.from_user.id] = "price"

    await m.answer("💰 Kanalga qoʻshilish narxini kiriting")

# ================= PRICE =================
@dp.message(F.text, lambda m: state.get(m.from_user.id) == "price")
async def price(m: types.Message):
    temp[m.from_user.id]["price"] = m.text
    state[m.from_user.id] = "card"

    await m.answer("💳 Kartangizni yuboring")

# ================= CARD =================
@dp.message(F.text, lambda m: state.get(m.from_user.id) == "card")
async def card(m: types.Message):
    data = temp[m.from_user.id]
    code = generate_code()

    cur.execute(
        "INSERT INTO orders (owner_id, channel_id, price, card, code) VALUES (?, ?, ?, ?, ?)",
        (m.from_user.id, str(data["channel"]), data["price"], m.text, code)
    )
    conn.commit()

    await m.answer(f"🔑 Sizning kanalingiz kod raqami: {code}")

    state.pop(m.from_user.id)
    temp.pop(m.from_user.id)

# ================= JOIN =================
@dp.message(F.text == "🔗 Qo‘shilish")
async def join(m: types.Message):
    state[m.from_user.id] = "code"
    await m.answer("🔑 Kod raqamni  yuboring")

# ================= SHOW =================
@dp.message(F.text, lambda m: state.get(m.from_user.id) == "code")
async def show(m: types.Message):
    cur.execute("SELECT * FROM orders WHERE code=?", (m.text,))
    order = cur.fetchone()

    if not order:
        await m.answer("❌ Kod raqam notoʻgʻri kiritildi va kanal topilmadi")
        return

    temp[m.from_user.id] = {"order": order}

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="buyconfirm")]
    ])

    await m.answer(
        f"💰 Narx: {order[3]}\n💳 {order[4]}",
        reply_markup=kb
    )

# ================= CONFIRM =================
@dp.callback_query(F.data == "buyconfirm")
async def buyconfirm(c: types.CallbackQuery):
    await c.message.answer("📸 Chek yuboring")
    state[c.from_user.id] = "buycheck"

# ================= BUY CHECK =================
@dp.message(F.photo, lambda m: state.get(m.from_user.id) == "buycheck")
async def buy_check(m: types.Message):
    order = temp[m.from_user.id]["order"]

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅", callback_data=f"approve_{m.from_user.id}")],
        [InlineKeyboardButton(text="❌", callback_data=f"reject_{m.from_user.id}")]
    ])

    await bot.send_photo(
        order[1],
        m.photo[-1].file_id,
        caption=f"💰 Xaridor: {m.from_user.id}",
        reply_markup=kb
    )

    await m.answer("✅Chek qabul qilindi\n⏳Admin tasdiqlashini kuting...")
    state[m.from_user.id] = "wait"

# ================= APPROVE =================
@dp.callback_query(F.data.startswith("approve_"))
async def approve(c: types.CallbackQuery):
    user_id = int(c.data.split("_")[1])

    cur.execute("SELECT * FROM orders WHERE owner_id=?", (c.from_user.id,))
    order = cur.fetchone()

    invite = await bot.create_chat_invite_link(
        chat_id=order[2],
        member_limit=1
    )

    await bot.send_message(user_id, f"🔗 Link:\n{invite.invite_link}")
    await c.message.edit_caption("✅ Toʻlov tasdiqlandi")

# ================= REJECT =================
@dp.callback_query(F.data.startswith("reject_"))
async def reject(c: types.CallbackQuery):
    user_id = int(c.data.split("_")[1])
    await bot.send_message(user_id, "❌ Toʻlov bekor qilindi")
    await c.message.edit_caption("❌")

# ================= FASTAPI =================
app = FastAPI()

@app.on_event("startup")
async def startup():
    await bot.set_webhook(WEBHOOK_URL)

@app.post(WEBHOOK_PATH)
async def webhook(req: Request):
    data = await req.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}

@app.get("/")
async def home():
    return {"status": "running"}

# ================= RUN =================
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
