import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import state
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, message
from database import Database
# Bot konfiguratsiyasi
API_TOKEN = "7803531348:AAGlMqXNsquMnXamijx_MTTc78dLI1SajQs"
ADMIN_IDS = [6248658681]  # Admin ID lari
CHANEL_ID=  -1002676385216

# Majburiy obuna bo'lish uchun kanallar
REQUIRED_CHANNELS = [
    {"id": "@Kampyuter_bilimlari_0dan", "name": "Kompyuter Bilimlari", "url": "https://t.me/Kampyuter_bilimlari_0dan"},
]
# Loglashni sozlash
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot obyektlari
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
db = Database()


# FSM holatlari
class Form(StatesGroup):
    waiting_for_phone = State()
    waiting_for_promo = State()
    waiting_for_withdraw_amount = State()
    waiting_for_withdraw_method = State()
    admin_send_message = State()
    admin_add_balance = State()


# Yordamchi funksiyalar
async def check_subscriptions(user_id: int) -> bool:
    """Foydalanuvchi barcha majburiy kanallarga obuna bo'lganligini tekshiradi"""
    try:
        for channel in REQUIRED_CHANNELS:
            chat_member = await bot.get_chat_member(chat_id=channel["id"], user_id=user_id)
            if chat_member.status not in ("member", "administrator", "creator"):
                return False
        return True
    except Exception as e:
        logger.error(f"Obunani tekshirishda xato: {e}")
        return False


# Asosiy menyu
async def show_main_menu(user_id: int, referrer_id=None):
    user = db.get_user(user_id)
    if not user:
        return

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("👥 Mening referallarim"))
    keyboard.add(types.KeyboardButton("💰 Balans"),
                 types.KeyboardButton("📊 Statistika"))
    keyboard.add(types.KeyboardButton("📢 Referal havolam"),
                 types.KeyboardButton("ℹ️ Yordam"))

    if user_id in ADMIN_IDS:
        keyboard.add(types.KeyboardButton("👑 Admin panel"))

    await bot.send_message(
        user_id,
        f"🏠 Asosiy menyu\n\n"
        f"👤 Sizning ID: {user['user_id']}\n"
        f"💰 Balans: {user['balance']} so'm\n"
        f"👥 Referallar: {db.get_referrals_count(user_id)} ta",
        reply_markup=keyboard
    )
# /start komandasi
@dp.message_handler(commands=['start'], state='*')
async def cmd_start(message: types.Message, state: FSMContext):
    await state.finish()

    # Obunani tekshirish
    if not await check_subscriptions(message.from_user.id):
        keyboard = InlineKeyboardMarkup()

        # ✅ TO‘G‘RI tugmalar
        for channel in REQUIRED_CHANNELS:
            keyboard.add(InlineKeyboardButton(f"📢 {channel['name']}", url=channel["url"]))

        # YouTube tugmasi
        keyboard.add(InlineKeyboardButton("▶️ YouTube kanalimiz", url="https://www.youtube.com/@NURIDDIN_0916"))

        # Tekshirish tugmasi
        keyboard.add(InlineKeyboardButton("✅ Tekshirish", callback_data="check_subs"))

        await message.answer(
            "📛 Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
            reply_markup=keyboard
        )
        return

    # Referal parametrini olish
    args = message.get_args()
    referrer_id = int(args) if args and args.isdigit() else None

    # Agar foydalanuvchi yangi bo'lsa
    if not db.get_user(message.from_user.id):
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(types.KeyboardButton("📱Ro'yxatdan o'tish", request_contact=True))

        await Form.waiting_for_phone.set()
        async with state.proxy() as data:
            data['referrer_id'] = referrer_id
        await message.answer("📞 Iltimos, telefon raqamingizni yuboring:", reply_markup=keyboard)
        return

    await show_main_menu(message.from_user.id)


@dp.callback_query_handler(lambda c: c.data == "check_subs")
async def check_again(callback: types.CallbackQuery, state: FSMContext):
    if not await check_subscriptions(callback.from_user.id):
        await callback.answer("⛔ Hali ham obuna emassiz!", show_alert=True)
    else:
        await callback.message.delete()
        await cmd_start(callback.message, state)


@dp.message_handler(content_types=types.ContentType.CONTACT, state=Form.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number
    async with state.proxy() as data:
        referrer_id = data.get('referrer_id')

    db.register_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
        referrer_id=referrer_id,
        phone=phone
    )

    await state.finish()
    await show_main_menu(message.from_user.id)


# Admin paneli uchun funksiyalar
@dp.message_handler(text="👑 Admin panel", user_id=ADMIN_IDS)
async def cmd_admin_panel(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("📊 Umumiy statistika"))
    keyboard.add(types.KeyboardButton("👀 Foydalanuvchilar ro'yxati"))
    keyboard.add(types.KeyboardButton("🏠 Asosiy menyu"))

    await message.answer("👑 Admin panel", reply_markup=keyboard)


@dp.message_handler(text="👀 Foydalanuvchilar ro'yxati", user_id=ADMIN_IDS)
async def show_users(message: types.Message):
    users = db.get_recent_users(20)

    if not users:
        await message.answer("ℹ️ Foydalanuvchilar topilmadi.")
        return

    text = "👥 Oxirgi 20 foydalanuvchi:\n\n"
    for user in users:
        reg_date = datetime.fromisoformat(user['registration_date']).strftime('%d.%m.%Y %H:%M')
        text += (
            f"👤 {user['full_name']} | @{user['username'] or 'nomalum'}\n"
            f"🆔 ID: {user['user_id']}\n"
            f"📱 Tel: {user.get('phone', 'yoq')}\n"
            f"💰 Balans: {user['balance']} so'm\n"
            f"📅 Ro'yxatdan o'tgan: {reg_date}\n\n"
        )

        await message.answer(text)

@dp.message_handler(text="📊 Umumiy statistika", user_id=ADMIN_IDS)
async def cmd_admin_stats(message: types.Message):
        total_users = db.get_total_users()
        total_referrals = db.get_total_referrals()
        total_paid = db.get_total_paid()
        top_referrers = db.get_top_referrers(5)

        text = (
            f"📊 Bot statistikasi:\n\n"
            f"👥 Jami foydalanuvchilar: {total_users} ta\n"
            f"🔗 Jami referallar: {total_referrals} ta\n"
            f"💰 Jami to'langan bonuslar: {total_paid} so'm\n\n"
            f"🏆 Eng yaxshi referallar:\n"
        )

        for i, ref in enumerate(top_referrers, 1):
            text += f"{i}. @{ref['username']} - {ref['referrals_count']} ta\n"

        await message.answer(text)
@dp.message_handler(text="🏠 Asosiy menyu", user_id=ADMIN_IDS)
async def back_to_main_menu(message: types.Message, state: FSMContext):
    await show_main_menu(message.from_user.id)

@dp.message_handler(lambda message: message.text == "ℹ️ Yordam")
async def help_handler(message: types.Message):
    await message.answer(
        "ℹ️ <b>Yordam bo‘limi</b>\n\n"
        "1. Ro‘yxatdan o‘tish uchun telefon raqamingizni yuboring.\n"
        "2. Referal havolangizni boshqalarga ulashib, daromad oling.\n"
        "3. Balansingiz yetarli bo‘lsa, yechib olishingiz mumkin.\n"
        "4. Qo‘shimcha savollar uchun admin bilan bog‘laning: @emereks_0916",
        parse_mode="HTML"
    )


    # Mening referallarim
@dp.message_handler(text="👥 Mening referallarim")
async def cmd_my_referrals(message: types.Message):
        user_id = message.from_user.id
        stats = db.get_referral_stats(user_id)
        recent_referrals = db.get_recent_referrals(user_id, 10)

        text = (
            f"📊 Referal statistikangiz:\n\n"
            f"🔢 Jami referallar: {stats['total']} ta\n"
            f"💰 Jami daromad: {stats['total_amount']} so'm\n"
            f"📈 Oxirgi 7 kun: {stats['weekly']} ta\n"
            f"📅 Bugun: {stats['daily']} ta\n\n"
            f"🔄 Oxirgi 10 ta referal:\n"
        )

        for ref in recent_referrals:
            ref_date = datetime.fromisoformat(ref['date']).strftime('%d.%m.%Y')
            text += f"👤 @{ref['username'] or ref['full_name']} - {ref_date}\n"

        await message.answer(text)

    # Balans
# 💰 Balans tugmasi bosilganda
@dp.message_handler(text="💰 Balans")
async def cmd_balance(message: types.Message):
    user = db.get_user(message.from_user.id)
    if not user:
        return

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("💳 Pul yechish", callback_data="withdraw"))

    await message.answer(
        f"💰 Sizning balansingiz: {user['balance']} so'm\n\n"
        f"Pul yechish uchun minimal summa: 3000 so'm",
        reply_markup=keyboard
    )

# 💳 Pul yechish tugmasi bosilganda
@dp.callback_query_handler(lambda c: c.data == "withdraw")
async def process_withdraw(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user = db.get_user(user_id)

    if not user:
        await callback.answer("❌ Foydalanuvchi topilmadi.", show_alert=True)
        return

    if user['balance'] < 3000:
        await callback.message.answer(
            "❌ Hisobingizdagi mablag' yetarli emas.\n"
            "Pul yechish uchun kamida 3000 so'm bo'lishi kerak."
        )
        return

    await callback.message.answer(
        "✅ Arizangiz qabul qilindi!\n\n"
        "💵 Tolov 9-12 soat ichida amalga oshiriladi. Ishonchingiz va kutganingiz uchun rahmat"
    )

    # Adminlarga xabar yuborish
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"📥 Pul yechish arizasi:\n\n"
                f"👤 ID: <code>{user_id}</code>\n"
                f"👤 Ismi: {user.get('full_name', 'Noma’lum')}\n"
                f"📱 Tel: {user.get('phone', 'Noma’lum')}\n"
                f"💰 Balans: {user['balance']} so'm",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Adminlarga xabar yuborishda xatolik: {e}")

    # Statistika
@dp.message_handler(text="📊 Statistika")
async def cmd_stats(message: types.Message):
        total_users = db.get_total_users()
        total_referrals = db.get_total_referrals()
        total_paid = db.get_total_paid()
        top_referrers = db.get_top_referrers(5)

        text = (
            f"📊 Bot statistikasi:\n\n"
            f"👥 Jami foydalanuvchilar: {total_users} ta\n"
            f"🔗 Jami referallar: {total_referrals} ta\n"
            f"💰 Jami to'langan bonuslar: {total_paid} so'm\n\n"
            f"🏆 Eng yaxshi referallar:\n"
        )

        for i, ref in enumerate(top_referrers, 1):
            text += f"{i}. @{ref['username']} - {ref['referrals_count']} ta\n"

        await message.answer(text)

    # Referal havolasi
@dp.message_handler(text="📢 Referal havolam")
async def cmd_referral_link(message: types.Message):
        user = db.get_user(message.from_user.id)
        if not user:
            return

        ref_link = f"https://t.me/{(await bot.get_me()).username}?start={user['user_id']}"
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("📢 Ulashish", switch_inline_query=f"Referal havolam: {ref_link}"))

        await message.answer(
            f"🔗 Sizning referal havolangiz:\n\n"
            f"{ref_link}\n\n"
            f"Har bir do'stingiz uchun sizga 300 so'm bonus!\n"
            f"Do'stlaringizni taklif qiling va daromadingizni oshiring!",
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
if __name__ == '__main__':
        from aiogram import executor
        executor.start_polling(dp, skip_updates=True)