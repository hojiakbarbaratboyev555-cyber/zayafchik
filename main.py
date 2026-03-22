import os
import logging
import random

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Update

logging.basicConfig(level=logging.INFO)

API_TOKEN = "8243006828:AAFFlt76hYWWMX_58fFfz1mgjinNtRQn7Uo"

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

app = FastAPI()

# 🔥 O'ZINGNI LINKING
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = "https://adminbot-jkfv.onrender.com/webhook"

# ---------------- DATA ----------------
admins = {}
pending_checks = {}
user_states = {}

# ---------------- START ----------------
@dp.message(Command("start"))
async def start(msg: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Buyurtma berish", callback_data="buyurtma")],
        [InlineKeyboardButton(text="🔑 Qo‘shilish", callback_data="qoshilish")]
    ])
    await msg.answer("Kerakli bo‘limni tanlang:", reply_markup=kb)


# ---------------- CALLBACK ----------------
@dp.callback_query()
async def callbacks(call: types.CallbackQuery):
    uid = call.from_user.id

    if call.data == "buyurtma":
        admins[uid] = {}
        user_states[uid] = "wait_channel"
        await call.message.answer("📢 Kanal yoki guruh ID yuboring:")

    elif call.data == "qoshilish":
        user_states[uid] = "wait_code"
        await call.message.answer("🔢 6 xonali kodni kiriting:")

    await call.answer()


# ---------------- TEXT ----------------
@dp.message()
async def text_handler(msg: types.Message):
    uid = msg.from_user.id
    text = msg.text
    state = user_states.get(uid)

    # ADMIN
    if state == "wait_channel":
        admins[uid]["channel_id"] = int(text)
        user_states[uid] = "wait_narx"
        await msg.answer("💰 Narx kiriting:")

    elif state == "wait_narx":
        admins[uid]["narx"] = text
        user_states[uid] = "wait_karta"
        await msg.answer("💳 Karta raqam kiriting:")

    elif state == "wait_karta":
        admins[uid]["karta"] = text
        user_states[uid] = "wait_group"
        await msg.answer("👥 Buyurtma guruhi ID:")

    elif state == "wait_group":
        admins[uid]["group_id"] = int(text)
        code = str(random.randint(100000, 999999))
        admins[uid]["code"] = code
        user_states[uid] = None
        await msg.answer(f"✅ Tayyor!\n\n🔑 Sizning kodingiz: {code}")

    # USER
    elif state == "wait_code":
        for admin_id, data in admins.items():
            if data.get("code") == text:
                user_states[uid] = "wait_check"
                admins[uid] = {"admin_id": admin_id}
                await msg.answer("📸 Chekni rasm qilib yuboring:")
                return

        await msg.answer("❌ Kod noto‘g‘ri")


# ---------------- PHOTO ----------------
@dp.message()
async def photo_handler(msg: types.Message):
    uid = msg.from_user.id

    if msg.content_type != "photo":
        return

    if user_states.get(uid) != "wait_check":
        return

    admin_id = admins[uid]["admin_id"]
    group_id = admins[admin_id]["group_id"]

    check_id = random.randint(10000, 99999)

    pending_checks[check_id] = {
        "user_id": uid,
        "admin_id": admin_id
    }

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"ok_{check_id}"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"no_{check_id}")
        ]
    ])

    await bot.send_photo(
        chat_id=group_id,
        photo=msg.photo[-1].file_id,
        caption="🧾 Yangi chek keldi",
        reply_markup=kb
    )

    await msg.answer("⏳ Yuborildi, admin tekshiradi")


# ---------------- ADMIN BUTTON ----------------
@dp.callback_query(lambda c: c.data.startswith("ok_") or c.data.startswith("no_"))
async def admin_buttons(call: types.CallbackQuery):
    check_id = int(call.data.split("_")[1])

    if check_id not in pending_checks:
        return await call.answer("Eskirgan")

    user_id = pending_checks[check_id]["user_id"]
    admin_id = pending_checks[check_id]["admin_id"]

    if call.data.startswith("ok_"):
        link = await bot.create_chat_invite_link(
            chat_id=admins[admin_id]["channel_id"],
            member_limit=1
        )
        await bot.send_message(user_id, f"✅ Qabul qilindi!\n\n🔗 {link.invite_link}")
    else:
        await bot.send_message(user_id, "❌ Bekor qilindi")

    del pending_checks[check_id]
    await call.answer("Bajarildi")


# ---------------- WEBHOOK ----------------
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
def home():
    return {"status": "Bot ishlayapti"}


import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
