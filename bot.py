#!/usr/bin/env python3
import stripe
import os
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler

TOKEN = "8959251314:AAEsEd8yBSftXS9FaL-NuyGJ4ZmQ6LTcE50"
STRIPE_SECRET_KEY = "sk_test_51TrC5AJtqeaVUBshTb8HMfLbJzDqHg3Pv681rZJbmioSI7BijLwTHTJQom7i9zRXh7jTwnqOhn1Mhc0uYAu4Ce6k00EsLuS7Xi"

stripe.api_key = STRIPE_SECRET_KEY

CHECKING = False
CARDS_LIST = []
APPROVED_LIST = []
DECLINED_LIST = []
INVALID_LIST = []
TOTAL_CARDS = 0

def luhn_check(card_number):
    if not card_number.isdigit(): return False
    digits = [int(d) for d in str(card_number)][::-1]
    for i in range(1, len(digits), 2):
        digits[i] *= 2
        if digits[i] > 9: digits[i] -= 9
    return sum(digits) % 10 == 0

def check_card_stripe(card_number, exp_month, exp_year, cvc):
    try:
        payment_method = stripe.PaymentMethod.create(
            type="card",
            card={
                "number": card_number,
                "exp_month": int(exp_month),
                "exp_year": int(exp_year),
                "cvc": cvc,
            },
        )
        stripe.SetupIntent.create(payment_method=payment_method.id, confirm=True)
        return "APPROVED", "✅ Live - Approved"
    except stripe.error.CardError as e:
        error = str(e).lower()
        if "insufficient_funds" in error: return "APPROVED", "✅ Live - Insufficient Funds"
        elif "card_declined" in error: return "DECLINED", "❌ Declined - Card Declined"
        elif "expired_card" in error: return "DECLINED", "❌ Declined - Card Expired"
        elif "incorrect_cvc" in error: return "DECLINED", "❌ Declined - Incorrect CVC"
        else: return "DECLINED", f"❌ Declined - {str(e)[:30]}"
    except Exception as e:
        return "DECLINED", f"❌ Error - {str(e)[:30]}"

def process_single_card(card_data):
    card_num = card_data['card'].strip()
    exp_month = card_data['month'].strip()
    exp_year = card_data['year'].strip()
    cvc = card_data['cvc'].strip()
    if not card_num.isdigit() or len(card_num) < 15: return "INVALID", "⚠️ Invalid - Wrong Format"
    if not luhn_check(card_num): return "INVALID", "⚠️ Invalid - Luhn Failed"
    return check_card_stripe(card_num, exp_month, exp_year, cvc)

async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("🤖 **CC Checker Bot**\n\n📁 فایلێکی .txt باربکە...", parse_mode='Markdown')

async def handle_file(update: Update, context: CallbackContext):
    global CHECKING, CARDS_LIST, TOTAL_CARDS, APPROVED_LIST, DECLINED_LIST, INVALID_LIST
    doc = update.message.document
    if not doc.file_name.endswith('.txt'):
        await update.message.reply_text("❌ تکایە فایلێکی .txt باربکە!")
        return
    file = await context.bot.get_file(doc.file_id)
    file_path = f"temp_{update.message.chat_id}.txt"
    await file.download_to_drive(file_path)
    try:
        with open(file_path, 'r') as f: lines = f.readlines()
    except:
        await update.message.reply_text("❌ نەتوانرا فایلەکە بخوێنرێتەوە")
        os.remove(file_path); return
    os.remove(file_path)
    CARDS_LIST = []
    for line in lines:
        line = line.strip()
        if not line: continue
        parts = line.split('|')
        if len(parts) >= 4:
            CARDS_LIST.append({'card': parts[0], 'month': parts[1], 'year': parts[2], 'cvc': parts[3]})
    if not CARDS_LIST:
        await update.message.reply_text("❌ هیچ کارتێک نەدۆزرایەوە!")
        return
    TOTAL_CARDS = len(CARDS_LIST)
    APPROVED_LIST = []; DECLINED_LIST = []; INVALID_LIST = []
    CHECKING = True
    await update.message.reply_text(f"📁 فایل وەرگیرا!\n📊 کۆی کارتەکان: {TOTAL_CARDS}\n⏳ پشکنین دەستی پێکرد...")
    await process_cards(update, context)

async def process_cards(update: Update, context: CallbackContext):
    global CHECKING, APPROVED_LIST, DECLINED_LIST, INVALID_LIST
    keyboard = [[InlineKeyboardButton("🛑 Stop", callback_data='stop')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = await update.message.reply_text(f"⏳ پشکنین دەکرێت...\n0/{TOTAL_CARDS}", reply_markup=reply_markup)
    for i, card_data in enumerate(CARDS_LIST):
        if not CHECKING:
            await msg.edit_text("🛑 پشکنین ڕاگرا!"); break
        masked = f"{card_data['card'][:4]}****{card_data['card'][-4:]}"
        status, message = process_single_card(card_data)
        if status == "APPROVED": APPROVED_LIST.append(f"✅ {masked} → {message}")
        elif status == "DECLINED": DECLINED_LIST.append(f"❌ {masked} → {message}")
        else: INVALID_LIST.append(f"⚠️ {masked} → {message}")
        if i % 3 == 0 or i == TOTAL_CARDS - 1:
            try:
                await msg.edit_text(f"⏳ پشکنین دەکرێت...\n✅ Approved: {len(APPROVED_LIST)}\n❌ Declined: {len(DECLINED_LIST)}\n⚠️ Invalid: {len(INVALID_LIST)}\n📊 پێشکەوتن: {i+1}/{TOTAL_CARDS}", reply_markup=reply_markup)
            except: pass
        await asyncio.sleep(0.3)
    if CHECKING:
        CHECKING = False
        await msg.edit_text(f"✅ **پشکنین تەواو بوو!**\n\n✅ Approved: {len(APPROVED_LIST)}\n❌ Declined: {len(DECLINED_LIST)}\n⚠️ Invalid: {len(INVALID_LIST)}\n📊 Total: {TOTAL_CARDS}", parse_mode='Markdown')
        if APPROVED_LIST:
            with open("approved.txt", "w") as f: f.write("\n".join(APPROVED_LIST))
            await update.message.reply_document(document=open("approved.txt", "rb"), caption=f"✅ {len(APPROVED_LIST)} Approved Cards")
            os.remove("approved.txt")
        if DECLINED_LIST:
            with open("declined.txt", "w") as f: f.write("\n".join(DECLINED_LIST))
            await update.message.reply_document(document=open("declined.txt", "rb"), caption=f"❌ {len(DECLINED_LIST)} Declined Cards")
            os.remove("declined.txt")

async def stop_check(update: Update, context: CallbackContext):
    global CHECKING
    query = update.callback_query
    await query.answer()
    CHECKING = False
    await query.edit_message_text("🛑 پشکنین ڕاگرا!")

def main():
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(CallbackQueryHandler(stop_check, pattern='stop'))
    print("🤖 بۆتەکە کارا بوو!")
    # گۆڕانکاری گرنگ: `allowed_updates` لابرا
    app.run_polling()

if __name__ == "__main__":
    main()
