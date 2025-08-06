import re
import requests
import asyncio
import logging
import json
import os
from typing import Dict

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import (
    Message, PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    LabeledPrice, FSInputFile, CallbackQuery
)
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

# === CONSTANTS ===
API_TOKEN = "7935311115:AAFoUmciAMNd671po-PT5nef2JG6JHKHzIc"
PAYMENT_PROVIDER_TOKEN = "ВАШ_ТОКЕН_ПЛАТЕЖНОГО_ПРОВАЙДЕРА"
CHANNEL_LINK = "https://t.me/borz_c"
BOT_USERNAME = "randomnygiftsbot"
TG_API = f"https://api.telegram.org/bot{API_TOKEN}"
OWNER_ID = 7455532203  # ← ВСТАВЬ СВОЙ user_id

# === INIT BOT ===
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# === STATE ===
session_state: Dict[int, dict] = {}
auto_purchase_config: Dict[int, int] = {}
gift_cache = set()
REFERRALS_FILE = "referrals.json"

# === UTILS ===
def load_json(file):
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump({}, f)
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f)

def get_available_gifts():
    try:
        response = requests.get(f"{TG_API}/getAvailableGifts")
        data = response.json()
        if data.get("ok"):
            return data.get("result", {}).get("gifts", [])
        else:
            return []
    except Exception as e:
        logging.warning(f"Error fetching gifts: {e}")
        return []

def send_gift(chat_id, gift_id):
    url = f"{TG_API}/sendGift"
    payload = {"user_id": chat_id, "gift_id": gift_id, "pay_for_upgrade": False}
    try:
        response = requests.post(url, json=payload)
        return response.ok
    except Exception as e:
        logging.warning(f"Error sending gift: {e}")
        return False

# === /start ===
@dp.message(Command("start"))
async def handle_start(message: Message):
    user_id = str(message.from_user.id)
    referrals = load_json(REFERRALS_FILE)
    text = "\U0001F340 Try your luck in Random NFT Gifts!"

    new_user = False
    referrer_id = None

    if message.text.startswith("/start ") and user_id not in referrals:
        ref_id = message.text.split()[1]
        if ref_id != user_id:
            referrer_id = ref_id
            new_user = True
            referrals[user_id] = {"points": 0, "referrals": []}
            if referrer_id not in referrals:
                referrals[referrer_id] = {"points": 5, "referrals": [user_id]}
            else:
                if user_id not in referrals[referrer_id]["referrals"]:
                    referrals[referrer_id]["points"] += 5
                    referrals[referrer_id]["referrals"].append(user_id)
            save_json(REFERRALS_FILE, referrals)
    elif user_id not in referrals:
        referrals[user_id] = {"points": 0, "referrals": []}
        save_json(REFERRALS_FILE, referrals)

    photo_path = "photo_2025-05-13_12-09-42.jpg"  # Убедись, что файл есть в папке с ботом
    photo = FSInputFile(photo_path)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Community", url=CHANNEL_LINK)],
        [InlineKeyboardButton(text="Earn Points✰", callback_data="ref_link")]
    ])
    await message.answer_photo(photo=photo, caption=text, reply_markup=keyboard)

    if new_user and referrer_id:
        try:
            await bot.send_message(int(referrer_id), "👤 A new user has followed your link. Your balance has been updated!")
        except Exception as e:
            logging.warning(f"Error notifying referrer {referrer_id}: {e}")

@dp.callback_query(F.data == "ref_link")
async def show_referral_link(callback_query: CallbackQuery):
    user_id = str(callback_query.from_user.id)
    referrals = load_json(REFERRALS_FILE)
    user_data = referrals.get(user_id, {"points": 0, "referrals": []})
    referral_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
    text = (
        f"🔗 <b>Your referral link:</b>\n{referral_link}\n\n"
        f"👥 Invited users: <b>{len(user_data['referrals'])}</b>\n"
        f"💰 Your points: <b>{user_data['points']}✶</b>\n\n"
        "Invite friends and get <b>5✶ points</b> for each new user!"
    )
    await callback_query.message.answer(text)
    await callback_query.answer()

@dp.message(Command("start1"))
async def start1(message: Message):
    if message.from_user.id != OWNER_ID:
        await message.answer("❌ Access denied.")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Available Gifts", callback_data="show_gifts")],
        [InlineKeyboardButton(text="⚙️ Auto Purchase", callback_data="auto_purchase")]
    ])
    await message.answer("Welcome! I will help you with Telegram gifts 🎁", reply_markup=keyboard)


@dp.callback_query(F.data == "show_gifts")
async def show_gifts(cb: CallbackQuery):
    gifts = get_available_gifts()
    if not gifts:
        await cb.message.edit_text("❌ No gifts available.")
        return

    keyboard = []
    for g in gifts:
        emoji = g.get("sticker", {}).get("emoji", "🎁")
        stars = g.get("star_count", 0)
        remaining = g.get("remaining_count")
        total = g.get("total_count")
        gift_id = g.get("id")

        # Формируем подпись с учётом наличия данных
        if remaining is not None and total is not None:
            label = f"{emoji} {stars}⭐ ({remaining}/{total})"
        else:
            label = f"{emoji} {stars}⭐"

        keyboard.append([
            InlineKeyboardButton(text=label, callback_data=f"select_{gift_id}")
        ])

    # Добавляем кнопку назад
    keyboard.append([InlineKeyboardButton(text="🔙 Back", callback_data="back")])

    await cb.message.edit_text("🎁 Choose a gift:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@dp.callback_query(F.data == "back")
async def go_back(cb: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Available Gifts", callback_data="show_gifts")],
        [InlineKeyboardButton(text="⚙️ Auto Purchase", callback_data="auto_purchase")]
    ])
    await cb.message.edit_text("Welcome! I will help you with Telegram gifts 🎁", reply_markup=keyboard)


@dp.callback_query(F.data.startswith("select_"))
async def choose_gift(cb: CallbackQuery):
    gift_id = cb.data.split("_", 1)[1]
    session_state[cb.from_user.id] = {"gift_id": gift_id}
    kb = [[
        InlineKeyboardButton(text="📥 Send to me", callback_data="send_me"),
        InlineKeyboardButton(text="📤 Send to Channel", callback_data="send_channel")
    ]]
    await cb.message.edit_text("Choose recipient:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "send_me")
async def send_to_self(cb: CallbackQuery):
    data = session_state.get(cb.from_user.id)
    if not data:
        await cb.message.answer("❌ Select a gift first.")
        return
    if send_gift(cb.from_user.id, data["gift_id"]):
        await cb.message.answer("🎁 Gift sent to yourself!")
    else:
        await cb.message.answer("❌ Error sending gift.")
    session_state.pop(cb.from_user.id, None)

@dp.callback_query(F.data == "auto_purchase")
async def auto_purchase(cb: CallbackQuery):
    user_id = cb.from_user.id
    if user_id in auto_purchase_config:
        text = f"🔁 Auto-purchase is ON: {auto_purchase_config[user_id]} pcs.\nTurn off?"
        kb = [[InlineKeyboardButton(text="❌ Disable", callback_data="disable_auto")]]
    else:
        session_state[user_id] = {"awaiting_auto": True}
        text = "🔁 Send count for each new gift:"
        kb = []
    kb.append([InlineKeyboardButton(text="🔙 Back", callback_data="back")])
    await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "disable_auto")
async def disable_auto(cb: CallbackQuery):
    auto_purchase_config.pop(cb.from_user.id, None)
    await cb.message.edit_text("❌ Auto-purchase disabled.")

@dp.message()
async def catch_auto_input(msg: Message):
    if session_state.get(msg.from_user.id, {}).get("awaiting_auto"):
        try:
            count = int(msg.text)
            if count > 0:
                auto_purchase_config[msg.from_user.id] = count
                await msg.answer(f"✅ Auto-purchase set: {count} pcs.")
                session_state.pop(msg.from_user.id, None)
            else:
                raise ValueError
        except:
            await msg.answer("❌ Enter valid number (e.g., 3)")

@dp.message(Command("get"))
async def handle_get_invoice_link(message: Message):
    parts = message.text.strip().split()

    if len(parts) != 2:
        await message.answer("❗ Используй: /get <сумма> (например: /get 10)")
        return

    amount_str = parts[1]

    if not amount_str.isdigit():
        await message.answer("❌ Введи корректное число (например: 3)")
        return

    amount = int(amount_str)
    if amount <= 0:
        await message.answer("❗ Сумма должна быть положительным числом.")
        return

    try:
        invoice_link = await bot.create_invoice_link(
            title=f"Покупка {amount} XTR",
            description=f"Оплата {amount} XTR",
            provider_token=PAYMENT_PROVIDER_TOKEN,
            currency="XTR",
            prices=[LabeledPrice(label=f"{amount} XTR", amount=amount)],
            payload=f"purchase_{amount}_xtr"
        )
        await message.answer(f"🔗 Ссылка для оплаты {amount} XTR:\n{invoice_link}")
    except Exception as e:
        await message.answer("❗ Произошла ошибка, попробуйте позже.")
        print(f"Ошибка в /get: {e}")



# === Обработка успешной оплаты
@dp.pre_checkout_query()
async def pre_checkout(pre_checkout_q: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)

@dp.message(F.successful_payment)
async def payment_success(message: Message):
    await message.answer("✅ Payment received! Thank you!")

# === /refund101 === возврат платежа
@dp.message(Command("refund101"))
async def handle_refund(message: Message):
    await message.answer("💳 Enter transaction ID (e.g. stxFTN...)")

@dp.message(F.text.startswith("stx"))
async def receive_transaction_id(msg: Message):
    try:
        await bot.refund_star_payment(user_id=msg.from_user.id, telegram_payment_charge_id=msg.text.strip())
        await msg.answer("✅ Success: Stars refunded!")
    except TelegramBadRequest as error:
        msg_txt = "❌ Error"
        if "CHARGE_NOT_FOUND" in error.message:
            msg_txt = "❌ Code not found."
        elif "ALREADY_REFUNDED" in error.message:
            msg_txt = "⚠️ Already refunded."
        await msg.answer(msg_txt)

# === Фоновый цикл авто-покупки подарков ===
async def gift_auto_loop():
    while True:
        gifts = get_available_gifts()
        new_gifts = [g for g in gifts if g.get("id") and g["id"] not in gift_cache]
        for gift in new_gifts:
            gift_cache.add(gift["id"])
            for user_id, count in auto_purchase_config.items():
                for _ in range(count):
                    send_gift(user_id, gift["id"])
                    await asyncio.sleep(0.1)
        await asyncio.sleep(1)

# === Запуск бота ===
async def main():
    asyncio.create_task(gift_auto_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())

