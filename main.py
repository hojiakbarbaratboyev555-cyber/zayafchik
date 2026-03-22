import os
import logging
import random
import sqlite3
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Update

logging.basicConfig(level=logging.INFO)

# ---------------- TOKEN ----------------
API_TOKEN = "8243006828:AAFFlt76hYWWMX_58fFfz1mgjinNtRQn7Uo"

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

app = FastAPI()

# ---------------- WEBHOOK ----------------
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"https://zayafchik.onrender.com{WEBHOOK_PATH}"

# ---------------- DATABASE ----------------
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

# Adminlar va buyurtmalar jadvali
cursor.execute("""
CREATE TABLE IF NOT EXISTS admins (
    user_id INTEGER PRIMARY KEY,
    channel_id INTEGER,
    narx TEXT,
    karta TEXT,
    group_id INTEGER,
    code TEXT
)
""")

# Buyurtma yuborgan foydalanuvchilar
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    admin_id INTEGER,
    state TEXT
)
""")

# Pending cheklar
cursor.execute("""
CREATE TABLE IF NOT EXISTS checks (
    check_id INTEGER PRIMARY KEY,
    user_id INTEGER,
    admin_id INTEGER
)
""")
conn.commit()

# ---------------- HELP FUNCTIONS ----------------
def set_user_state(user_id: int, state: str):
    cursor.execute("INSERT OR REPLACE INTO users (user_id, state) VALUES (?, ?)", (user_id, state))
    conn.commit()

def get_user_state(user_id: int):
    cursor.execute("SELECT state FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    return row[0] if row else None

def set_user_admin(user_id: int, admin_id: int):
    cursor.execute("INSERT OR REPLACE INTO users (user_id, admin_id) VALUES (?, ?)", (user_id, admin_id))
    conn.commit()

def get_admin_by_code(code: str):
    cursor.execute("SELECT * FROM admins WHERE code=?", (code,))
    return cursor.fetchone()

def add_check(check_id: int, user_id: int, admin_id: int):
    cursor.execute("INSERT INTO checks (check_id, user_id, admin_id) VALUES (?, ?, ?)", (check_id, user_id, admin_id))
    conn.commit()

def remove_check(check_id: int):
    cursor.execute("DELETE FROM checks WHERE check_id=?", (check_id,))
    conn.commit()

def get_check(check_id: int):
    cursor.execute("SELECT * FROM checks WHERE check_id=?", (check_id,))
    return cursor.fetchone()

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
        set_user_state(uid, "wait_channel")
        await call.message.answer("📢 Kanal yoki guruh ID yuboring:")
    elif call.data == "qoshilish":
        set_user_state(uid, "wait_code")
        await call.message.answer("🔢 6 xonali kodni kiriting:")
    await call.answer()

# ---------------- TEXT HANDLER ----------------
@dp.message()
async def text_handler(msg: types.Message):
    uid = msg.from_user.id
    text = msg.text
    state = get_user_state(uid)

    # ---------- ADMIN FLOW ----------
    if state == "wait_channel":
        try:
            channel_id = int(text)
        except:
            return await msg.answer("❌ ID raqam bo‘lishi kerak")
        cursor.execute("INSERT OR REPLACE INTO admins (user_id, channel_id) VALUES (?, ?)", (uid, channel_id))
        conn.commit()
        set_user_state(uid, "wait_narx")
        await msg.answer("💰 Obuna narxini kiriting:")

    elif state == "wait_narx":
        cursor.execute("UPDATE admins SET narx=? WHERE user_id=?", (text, uid))
        conn.commit()
        set_user_state(uid, "wait_karta")
        await msg.answer("💳 16 xonali karta raqamini kiriting:")

    elif state == "wait_karta":
        if not text.isdigit() or len(text) != 16:
            return await msg.answer("❌ Karta noto‘g‘ri. 16 xonali raqam kiriting.")
        cursor.execute("UPDATE admins SET karta=? WHERE user_id=?", (text, uid))
        conn.commit()
        set_user_state(uid, "wait_group")
        await msg.answer("👥 Buyurtma guruhi ID yuboring:")

    elif state == "wait_group":
        try:
            group_id = int(text)
        except:
            return await msg.answer("❌ ID raqam bo‘lishi kerak")
        code = str(random.randint(100000, 999999))
        cursor.execute("UPDATE admins SET group_id=?, code=? WHERE user_id=?", (group_id, code, uid))
        conn.commit()
        set_user_state(uid, None)
        await msg.answer(f"✅ Tayyor!\n🔑 Sizning kodingiz: {code}")

    # ---------- USER FLOW ----------
    elif state == "wait_code":
        admin_data = get_admin_by_code(text)
        if not admin_data:
            return await msg.answer("❌ Kod noto‘g‘ri")
        admin_id = admin_data[0]
        set_user_state(uid, "wait_check")
        set_user_admin(uid, admin_id)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("Tasdiqlash", callback_data="confirm_pay")]
        ])
        await msg.answer(
            f"💰 Obuna narxi: {admin_data[2]}\n💳 Karta: {admin_data[3]}\n\n"
            "To‘lov qilgandan so‘ng pastdagi tugmani bosing va chekni yuboring:",
            reply_markup=kb
        )

# ---------------- TASDIQLASH ----------------
@dp.callback_query(lambda c: c.data == "confirm_pay")
async def confirm_pay(call: types.CallbackQuery):
    uid = call.from_user.id
    set_user_state(uid, "wait_check")
    await call.message.answer("📸 Chekni rasm qilib yuboring:")
    await call.answer()

# ---------------- PHOTO HANDLER ----------------
@dp.message()
async def photo_handler(msg: types.Message):
    uid = msg.from_user.id
    if msg.content_type != "photo":
        return
    if get_user_state(uid) != "wait_check":
        return

    cursor.execute("SELECT admin_id FROM users WHERE user_id=?", (uid,))
    row = cursor.fetchone()
    if not row:
        return await msg.answer("❌ Xato")
    admin_id = row[0]

    cursor.execute("SELECT group_id FROM admins WHERE user_id=?", (admin_id,))
    group_id = cursor.fetchone()[0]

    check_id = random.randint(10000, 99999)
    add_check(check_id, uid, admin_id)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"ok_{check_id}"),
            InlineKeyboardButton("❌ Bekor qilish", callback_data=f"no_{check_id}")
        ]
    ])

    await bot.send_photo(
        chat_id=group_id,
        photo=msg.photo[-1].file_id,
        caption="🧾 Yangi chek keldi",
        reply_markup=kb
    )
    await msg.answer("⏳ Chek yuborildi, admin tekshiradi")

# ---------------- ADMIN BUTTON ----------------
@dp.callback_query(lambda c: c.data.startswith("ok_") or c.data.startswith("no_"))
async def admin_buttons(call: types.CallbackQuery):
    check_id = int(call.data.split("_")[1])
    check = get_check(check_id)
    if not check:
        return await call.answer("Eskirgan")
    user_id, admin_id = check[1], check[2]

    cursor.execute("SELECT channel_id FROM admins WHERE user_id=?", (admin_id,))
    channel_id = cursor.fetchone()[0]

    if call.data.startswith("ok_"):
        try:
            link = await bot.create_chat_invite_link(chat_id=channel_id, member_limit=1)
            await bot.send_message(user_id, f"✅ Qabul qilindi!\n🔗 {link.invite_link}")
        except Exception as e:
            await bot.send_message(user_id, f"❌ Havola yaratishda xato: {e}")
    else:
        await bot.send_message(user_id, "❌ Adminlar qo‘shishdan bosh tortdi")

    remove_check(check_id)
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

# ---------------- RUN ----------------
import uvicorn
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
