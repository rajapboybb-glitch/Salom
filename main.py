import logging
import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

# ---------------- BOT SOZLAMALARI ----------------
BOT_TOKEN = "8842199834:AAGrxe8uxPrV-JdIM1dsrLnH0aSl4wdXqMk"  # BotFather tokenini kiriting
ADMIN_ID = 8923173548  # O'zingizning Telegram ID-ingiz
CHANNELS = ["@aniolam_uz"]  # Majburiy obuna kanallari

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# ---------------- BAZA SOZLAMALARI ----------------
def init_db():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            is_vip INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS animes (
            anime_id TEXT PRIMARY KEY,
            title TEXT,
            episodes_count INTEGER,
            quality TEXT,
            genre TEXT,
            channel TEXT,
            rating TEXT,
            photo TEXT,
            is_vip INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def add_user(user_id: int):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def set_vip_user(user_id: int):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (user_id, is_vip) VALUES (?, 1) ON CONFLICT(user_id) DO UPDATE SET is_vip=1", (user_id,))
    conn.commit()
    conn.close()

def is_user_vip(user_id: int) -> bool:
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT is_vip FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return bool(row and row[0] == 1)

def get_all_users():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

def add_anime_to_db(anime_id, title, episodes, quality, genre, photo, is_vip):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO animes (anime_id, title, episodes_count, quality, genre, channel, rating, photo, is_vip)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (anime_id, title, episodes, quality, genre, "@animoviy", "5.0 / 5", photo, 1 if is_vip else 0))
    conn.commit()
    conn.close()

def get_anime_by_id_or_title(query: str):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM animes WHERE anime_id = ? OR title LIKE ?", (query, f"%{query}%"))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "anime_id": row[0],
            "title": row[1],
            "episodes_count": row[2],
            "quality": row[3],
            "genre": row[4],
            "channel": row[5],
            "rating": row[6],
            "photo": row[7],
            "is_vip": bool(row[8])
        }
    return None

def get_vip_animes():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT anime_id, title FROM animes WHERE is_vip = 1")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_stats():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_vip = 1")
    total_vips = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM animes")
    total_animes = cursor.fetchone()[0]
    conn.close()
    return total_users, total_vips, total_animes

# ---------------- FSM (HOLATLAR) ----------------
class SearchState(StatesGroup):
    waiting_for_code = State()
    waiting_for_name = State()

class AdminState(StatesGroup):
    add_id = State()
    add_title = State()
    add_episodes = State()
    add_quality = State()
    add_genre = State()
    add_photo = State()
    add_is_vip = State()
    give_vip_user = State()
    broadcast_msg = State()

# ---------------- TUGMALAR ----------------
def get_main_menu(user_id: int):
    kb = [
        [KeyboardButton(text="🔎 Anime Izlash")],
        [KeyboardButton(text="👑 VIP Animelar"), KeyboardButton(text="💎 VIP Obuna")],
        [KeyboardButton(text="⚙️ Kabinet"), KeyboardButton(text="▶️ Shorts")],
        [KeyboardButton(text="📑 Qo'llanma"), KeyboardButton(text="📢 Reklama")]
    ]
    if user_id == ADMIN_ID:
        kb.append([KeyboardButton(text="🛠 Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_admin_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Anime qo'shish"), KeyboardButton(text="💎 VIP obuna berish")],
            [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📢 Reklama yuborish")],
            [KeyboardButton(text="⚙️ Bot Sozlamalari"), KeyboardButton(text="⬅️ Asosiy menyu")]
        ],
        resize_keyboard=True
    )

def get_search_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💳 Kod orqali izlash", callback_data="search_by_code"),
                InlineKeyboardButton(text="📝 Nom orqali izlash", callback_data="search_by_name")
            ]
        ]
    )

def get_subscription_keyboard():
    buttons = []
    for ch in CHANNELS:
        buttons.append([InlineKeyboardButton(text="Obuna bo'ling ↗️", url=f"https://t.me/{ch.replace('@', '')}")])
    buttons.append([InlineKeyboardButton(text="🔄 Tekshirish", callback_data="check_subscription")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_episodes_keyboard(anime_id: str, total_episodes: int):
    buttons = []
    row = []
    for ep in range(1, min(total_episodes + 1, 25)):
        row.append(InlineKeyboardButton(text=str(ep), callback_data=f"get_ep_{anime_id}_{ep}"))
        if len(row) == 6:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="⭐ Baholash", callback_data=f"rate_{anime_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ---------------- TEKSHIRUV VA HANDLERLAR ----------------
async def check_user_subscribed(user_id: int) -> bool:
    if is_user_vip(user_id):
        return True
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            return False
    return True

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    add_user(message.from_user.id)
    is_sub = await check_user_subscribed(message.from_user.id)
    if not is_sub:
        await message.answer(
            "❗️ **Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling yoki VIP obuna oling!**",
            reply_markup=get_subscription_keyboard(),
            parse_mode="Markdown"
        )
        return

    text = (
        "👋 **Assalomu aleykum botimizga xush kelibsiz.**\n\n"
        "📺 Botimizda animelarni tomosha qilishingiz mumkin!\n"
        "‼️ Anime kodini yuboring yoki izlash tugmasidan foydalaning."
    )
    await message.answer_photo(
        photo="https://picsum.photos/500/300",
        caption=text,
        reply_markup=get_main_menu(message.from_user.id),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "check_subscription")
async def check_sub_callback(callback: types.CallbackQuery):
    if await check_user_subscribed(callback.from_user.id):
        await callback.message.delete()
        await callback.message.answer("✅ Obuna tasdiqlandi!")
        await start_handler(callback.message)
    else:
        await callback.answer("❌ Hali hamma kanallarga obuna bo'lmadingiz!", show_alert=True)

@dp.message(F.text == "🔎 Anime Izlash")
async def search_menu_handler(message: types.Message):
    await message.answer("🔍 **Izlash bo'limi:**", reply_markup=get_search_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "search_by_code")
async def ask_code(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(SearchState.waiting_for_code)
    await callback.message.answer("🔢 **Anime kodini kiriting:**", parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "search_by_name")
async def ask_name(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(SearchState.waiting_for_name)
    await callback.message.answer("📝 **Anime nomini kiriting:**", parse_mode="Markdown")
    await callback.answer()

@dp.message(SearchState.waiting_for_code)
@dp.message(SearchState.waiting_for_name)
@dp.message(F.text)
async def process_search(message: types.Message, state: FSMContext):
    query = message.text.strip()
    await state.clear()

    anime = get_anime_by_id_or_title(query)

    if anime:
        if anime["is_vip"] and not is_user_vip(message.from_user.id):
            await message.answer("🔒 **Bu anime faqat VIP obunachilar uchun!** VIP obuna sotib olish uchun adminga murojaat qiling.")
            return

        caption = (
            f"🎬 **Anime nomi:** {anime['title']}\n\n"
            f"📊 **Holati:** {anime['episodes_count']} qism\n"
            f"🎬 **Sifat:** {anime['quality']}\n"
            f"🎭 **Janrlari:** {anime['genre']}\n"
            f"📢 **Kanal:** {anime['channel']}\n"
            f"⭐️ **Reyting:** {anime['rating']}\n"
            f"🆔 **Anime ID:** {anime['anime_id']}"
        )
        await message.answer_photo(
            photo=anime["photo"],
            caption=caption,
            reply_markup=get_episodes_keyboard(anime_id=anime['anime_id'], total_episodes=anime['episodes_count']),
            parse_mode="Markdown"
        )
    else:
        await message.answer("❌ **Afsuski, hech narsa topilmadi.**")

@dp.message(F.text == "👑 VIP Animelar")
async def vip_anime_list(message: types.Message):
    animes = get_vip_animes()
    if animes:
        text = "💎 **Eksklyuziv VIP Animelar ro'yxati:**\n\n" + "\n".join([f"🆔 `{aid}`: {title}" for aid, title in animes])
    else:
        text = "ℹ️ Hozircha VIP animelar mavjud emas."
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "💎 VIP Obuna")
async def vip_info(message: types.Message):
    text = (
        "💎 **VIP Obuna afzalliklari:**\n"
        "1. Majburiy kanallarga obuna bo'lish talab etilmaydi.\n"
        "2. Maxsus VIP animelarni tomosha qilish imkoniyati.\n\n"
        "Sotib olish uchun admin bilan bog'laning: @admin_username"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "🛠 Admin Panel")
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("🛠 **Admin panelliga xush kelibsiz!**", reply_markup=get_admin_menu(), parse_mode="Markdown")

@dp.message(F.text == "⬅️ Asosiy menyu")
async def back_to_main(message: types.Message):
    await message.answer("Asosiy menyu:", reply_markup=get_main_menu(message.from_user.id))

@dp.message(F.text == "📊 Statistika")
async def show_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    u_count, v_count, a_count = get_stats()
    text = (
        f"📊 **Bot Statistikasi:**\n\n"
        f"👤 Jami foydalanuvchilar: **{u_count}** ta\n"
        f"💎 VIP foydalanuvchilar: **{v_count}** ta\n"
        f"🎬 Jami animelar: **{a_count}** ta"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "💎 VIP obuna berish")
async def give_vip_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminState.give_vip_user)
    await message.answer("👤 VIP berish uchun foydalanuvchining **Telegram ID**-sini kiriting:")

@dp.message(AdminState.give_vip_user)
async def give_vip_process(message: types.Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        set_vip_user(user_id)
        await message.answer(f"✅ User ID: `{user_id}` VIP statusga ega bo'ldi!", parse_mode="Markdown")
    except ValueError:
        await message.answer("❌ Noto'g'ri ID kiritildi.")
    await state.clear()

@dp.message(F.text == "➕ Anime qo'shish")
async def add_anime_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminState.add_id)
    await message.answer("🆔 Yangi Anime **kodini (ID)** kiriting (masalan: 2):")

@dp.message(AdminState.add_id)
async def add_anime_id(message: types.Message, state: FSMContext):
    await state.update_data(id=message.text.strip())
    await state.set_state(AdminState.add_title)
    await message.answer("📝 Anime **nomini** kiriting:")

@dp.message(AdminState.add_title)
async def add_anime_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await state.set_state(AdminState.add_episodes)
    await message.answer("🔢 Qismlar sonini kiriting:")

@dp.message(AdminState.add_episodes)
async def add_anime_episodes(message: types.Message, state: FSMContext):
    await state.update_data(episodes=int(message.text.strip()))
    await state.set_state(AdminState.add_quality)
    await message.answer("🎬 Sifatini kiriting (masalan: 720p - 1080p):")

@dp.message(AdminState.add_quality)
async def add_anime_quality(message: types.Message, state: FSMContext):
    await state.update_data(quality=message.text.strip())
    await state.set_state(AdminState.add_genre)
    await message.answer("🎭 Janrini kiriting:")

@dp.message(AdminState.add_genre)
async def add_anime_genre(message: types.Message, state: FSMContext):
    await state.update_data(genre=message.text.strip())
    await state.set_state(AdminState.add_photo)
    await message.answer("🖼 Poster rasm URL manzilini kiriting:")

@dp.message(AdminState.add_photo)
async def add_anime_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo=message.text.strip())
    await state.set_state(AdminState.add_is_vip)
    await message.answer("💎 Bu anime VIP-mi? (ha / yo'q):")

@dp.message(AdminState.add_is_vip)
async def add_anime_is_vip(message: types.Message, state: FSMContext):
    data = await state.get_data()
    is_vip = message.text.strip().lower() == "ha"
    
    add_anime_to_db(
        data["id"],
        data["title"],
        data["episodes"],
        data["quality"],
        data["genre"],
        data["photo"],
        is_vip
    )
    await message.answer(f"✅ **{data['title']}** bazaga muvaffaqiyatli saqlandi!", parse_mode="Markdown")
    await state.clear()

@dp.message(F.text == "📢 Reklama yuborish")
async def broadcast_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminState.broadcast_msg)
    await message.answer("📢 Barcha foydalanuvchilarga yuboriladigan reklama xabarini kiriting:")

@dp.message(AdminState.broadcast_msg)
async def broadcast_send(message: types.Message, state: FSMContext):
    count = 0
    all_users = get_all_users()
    for uid in all_users:
        try:
            await message.send_copy(chat_id=uid)
            count += 1
        except Exception:
            pass
    await message.answer(f"✅ Reklama {count} ta foydalanuvchiga yuborildi.")
    await state.clear()

async def main():
    init_db()
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    