import logging
import os
import random
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ContentType
from aiohttp import web

API_TOKEN = "8243006828:AAFFlt76hYWWMX_58fFfz1mgjinNtRQn7Uo"

logging.basicConfig(level=logging.INFO)

bot = Bot(API_TOKEN)
dp = Dispatcher()

# ---------------- DATA ----------------
admins = {}  
# user_id: {channel_id, narx, karta, group_id, code}

pending_checks = {}  
# check_id: {user_id, admin_id}

user_states = {}  
# user_id: state

# ---------------- START ----------------
@dp.message(Command("start"))
async def start(msg: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Buyurtma berish", callback_data="buyurtma")],
        [InlineKeyboardButton(text="Qo‘shilish", callback_data="qoshilish")]
    ])
    await msg.answer("Tanlang:", reply_markup=kb)

# ---------------- CALLBACK ----------------
@dp.callback_query()
async def callbacks(call: types.CallbackQuery):
    uid = call.from_user.id

    # BUYURTMA
    if call.data == "buyurtma":
        admins[uid] = {}
        user_states[uid] = "wait_channel"
        await call.message.answer("Kanal yoki guruh ID yuboring:")
    
    # QO‘SHILISH
    elif call.data == "qoshilish":
        user_states[uid] = "wait_code"
        await call.message.answer("6 xonali kodni kiriting:")

    await call.answer()

# ---------------- TEXT HANDLER ----------------
@dp.message()
async def text_handler(msg: types.Message):
    uid = msg.from_user.id
    text = msg.text

    state = user_states.get(uid)

    # -------- ADMIN FLOW --------
    if state == "wait_channel":
        admins[uid]["channel_id"] = int(text)
        user_states[uid] = "wait_narx"
        await msg.answer("Narx kiriting:")
    
    elif state == "wait_narx":
        admins[uid]["narx"] = text
        user_states[uid] = "wait_karta"
        await msg.answer("16 xonali karta kiriting:")

    elif state == "wait_karta":
        if not text.isdigit() or len(text) != 16:
            return await msg.answer("❌ Karta noto‘g‘ri")
        
        admins[uid]["karta"] = text
        user_states[uid] = "wait_group"
        await msg.answer("Buyurtma guruhi ID yuboring:")

    elif state == "wait_group":
        admins[uid]["group_id"] = int(text)
        
        code = random.randint(100000, 999999)
        admins[uid]["code"] = str(code)

        user_states[uid] = None

        await msg.answer(f"✅ Tayyor!\nSizning kodingiz: {code}")

    # -------- USER FLOW --------
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
            [InlineKeyboardButton(text="Tasdiqlash", callback_data="confirm_pay")]
        ])

        await msg.answer(
            f"Narx: {data['narx']}\nKarta: {data['karta']}",
            reply_markup=kb
        )

# ---------------- INLINE ----------------
@dp.callback_query(lambda c: c.data == "confirm_pay")
async def confirm_pay(call: types.CallbackQuery):
    uid = call.from_user.id
    user_states[uid] = "wait_check"
    await call.message.answer("Chekni rasm qilib yuboring:")
    await call.answer()

# ---------------- PHOTO ----------------
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

# ---------------- ADMIN BUTTONS ----------------
@dp.callback_query(lambda c: c.data.startswith("ok_") or c.data.startswith("no_"))
async def admin_buttons(call: types.CallbackQuery):
    data = call.data
    check_id = int(data.split("_")[1])

    if check_id not in pending_checks:
        return await call.answer("Eskirgan")

    user_id = pending_checks[check_id]["user_id"]
    admin_id = pending_checks[check_id]["admin_id"]

    channel_id = admins[admin_id]["channel_id"]

    # TASDIQLASH
    if data.startswith("ok_"):
        link = await bot.create_chat_invite_link(
            chat_id=channel_id,
            member_limit=1
        )

        await bot.send_message(
            user_id,
            f"✅ Qabul qilindi!\nHavola:\n{link.invite_link}"
        )

    # BEKOR
    else:
        await bot.send_message(
            user_id,
            "❌ Adminlar sizni rad etdi"
        )

    del pending_checks[check_id]
    await call.answer("Bajarildi")

# ---------------- WEBHOOK ----------------
async def handle(request):
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(bot, update)
    return web.Response()

async def on_startup(app):
    await bot.set_webhook(os.getenv("WEBHOOK_URL"))

async def on_shutdown(app):
    await bot.delete_webhook()
    await bot.session.close()

app = web.Application()
app.router.add_post("/", handle)
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == "__main__":
    web.run_app(app, port=int(os.getenv("PORT", 8000)))
