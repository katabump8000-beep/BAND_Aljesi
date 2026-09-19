import os
import json
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# إعداد السجلات
logging.basicConfig(level=logging.INFO)

# جلب بيانات الاعتماد والمتغيرات من Railway
PO_EMAIL = os.getenv("PO_EMAIL")
PO_PASSWORD = os.getenv("PO_PASSWORD")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

def check_po_credentials():
    """التحقق من وجود بيانات الحساب"""
    if not PO_EMAIL or not PO_PASSWORD:
        return False, "بيانات PO_EMAIL أو PO_PASSWORD غير موجودة في Variables!"
    return True, "تم العثور على بيانات الحساب بنجاح"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("▶️ فحص الاتصال والتداول", callback_data="start_bot")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "أهلاً بك! البوت يعمل الآن على Railway بنجاح 🚀",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "start_bot":
        status, msg = check_po_credentials()
        if status:
            masked_email = PO_EMAIL[:3] + "***" if PO_EMAIL else "غير معروف"
            await query.edit_message_text(f"✅ البوت جاهز للعمل!\nالبريد المسجل: {masked_email}\nجاري جلب إشارات التحليل...")
        else:
            await query.edit_message_text(f"❌ خطأ: {msg}")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("Bot is running...")
    app.run_polling()
