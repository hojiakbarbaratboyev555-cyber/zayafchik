import os
import asyncio
import logging
import random

from fastapi import FastAPI
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ContentType
import uvicorn

logging.basicConfig(level=logging.INFO)

# ---------------- TOKEN ----------------
API_TOKEN = "8243006828:AAFFlt76hYWWMX_58fFfz1mgjinNtRQn7Uo"

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# ---------------- DATA ----------------
admins = {}  # admin user_id: data
pending_checks = {}  # check_id: {user_id, admin_id}
user_states = {}  # user_id: state

# ---------------- FASTAPI ----------------
app = FastAPI()


@app.on_event("startup")
async def on_startup():
    # webhook conflictlarini tozalash
    await bot.delete_webhook(drop_pending_updates=True)
    # pollingni backgroundda ishga tushurish
    try:
        asyncio.create_task(dp.start_polling(bot, skip_updates=True))
    except Exception as e:
        logging.error(f"Polling xato berdi: {e}")


@app.get("/")
def home():
    return {"status": "Bot ishlayapti"}

# ---------------- HANDLERLAR ----------------

@dp.message(commands=["start"])
async def start(msg: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("Buyurtma berish", callback_data="buyurtma")],
        [InlineKeyboardButton("Qo‘shilish", callback_data="qoshilish")]
    ])
    await msg.answer("Tanlang:", reply_markup=kb)


@dp.callback_query()
async def callbacks(call: types.CallbackQuery):
    uid = call.from_user.id
    if call.data == "buyurtma":
        admins[uid] = {}
        user_states[uid] = "wait_channel"
        await call.message.answer("Kanal yoki guruh ID yuboring:")
    elif call.data == "qoshilish":
        user_states[uid] = "wait_code"
        await call.message.answer("6 xonali kodni kiriting:")
    await call.answer()


@dp.message()
async def text_handler(msg: types.Message):
    uid = msg.from_user.id
    text = msg.text
    state = user_states.get(uid)

    # ---------- ADMIN FLOW ----------
    if state == "wait_channel":
        admins[uid]["channel_id"] = int(text)
        user_states[uid] = "wait_narx"
        await msg.answer("Obuna narxini kiriting:")

    elif state == "wait_narx":
        admins[uid]["narx"] = text
        user_states[uid] = "wait_karta"
        await msg.answer("16 xonali karta kiriting:")

    elif state == "wait_karta":
        if not text.isdigit() or len(text) != 16:
            return await msg.answer("❌ Karta noto‘g‘ri. 16 xonali raqam kiriting.")
        admins[uid]["karta"] = text
        user_states[uid] = "wait_group"
        await msg.answer("Buyurtma guruhi ID yuboring:")

    elif state == "wait_group":
        admins[uid]["group_id"] = int(text)
        # 6 xonali random kod
        code = str(random.randint(100000, 999999))
        admins[uid]["code"] = code
        user_states[uid] = None
        await msg.answer(f"✅ Tayyor!\nSizning kodingiz: {code}")

    # ---------- USER FLOW ----------
    elif state == "wait_code":
        found = None
        for admin_id, data in admins.items():
            if data.get("code") == text:
                found = admin_id
                break
        if not found:
            return await msg.answer("❌ Kod noto‘g‘ri")
        user_states[uid] = "confirm_pay"
        admins[uid] = {"admin_id": found}
        data = admins[found]
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("Tasdiqlash", callback_data="confirm_pay")]
        ])
        await msg.answer(
            f"Obuna narxi: {data['narx']}\nKarta: {data['karta']}\n\nTo‘lov qilgandan so‘ng pastdagi tugmani bosing va chekni yuboring",
            reply_markup=kb
        )


@dp.callback_query(lambda c: c.data == "confirm_pay")
async def confirm_pay(call: types.CallbackQuery):
    uid = call.from_user.id
    user_states[uid] = "wait_check"
    await call.message.answer("Chekni rasm qilib yuboring:")
    await call.answer()


@dp.message(lambda m: m.content_type == ContentType.PHOTO)
async def photo_handler(msg: types.Message):
    uid = msg.from_user.id
    if user_states.get(uid) != "wait_check":
        return
    admin_id = admins[uid]["admin_id"]
    group_id = admins[admin_id]["group_id"]
    check_id = random.randint(10000, 99999)
    pending_checks[check_id] = {"user_id": uid, "admin_id": admin_id}
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"ok_{check_id}"),
            InlineKeyboardButton("❌ Bekor qilish", callback_data=f"no_{check_id}")
        ]
    ])
    await bot.send_photo(
        group_id,
        msg.photo[-1].file_id,
        caption="Yangi chek",
        reply_markup=kb
    )
    await msg.answer("Chek yuborildi, kuting...")


@dp.callback_query(lambda c: c.data.startswith("ok_") or c.data.startswith("no_"))
async def admin_buttons(call: types.CallbackQuery):
    data = call.data
    check_id = int(data.split("_")[1])
    if check_id not in pending_checks:
        return await call.answer("Eskirgan")
    user_id = pending_checks[check_id]["user_id"]
    admin_id = pending_checks[check_id]["admin_id"]
    channel_id = admins[admin_id]["channel_id"]

    if data.startswith("ok_"):
        try:
            link = await bot.create_chat_invite_link(chat_id=channel_id, member_limit=1)
            await bot.send_message(user_id, f"✅ Qabul qilindi!\nHavola:\n{link.invite_link}")
        except Exception as e:
            await bot.send_message(user_id, f"❌ Link yaratishda xato: {e}")
    else:
        await bot.send_message(user_id, "❌ Adminlar sizni qo‘shishdan bosh tortishdi")
    del pending_checks[check_id]
    await call.answer("Bajarildi")


# ---------------- RUN ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
