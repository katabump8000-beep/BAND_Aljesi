import os
import time
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from pocketoptionapi.stable_api import PocketOption
from strategy import check_signal_and_trade

# إعداد السجلات
logging.basicConfig(level=logging.INFO)

# قراءة البيانات من متغيرات البيئة في Railway
PO_EMAIL = os.getenv("PO_EMAIL")
PO_PASSWORD = os.getenv("PO_PASSWORD")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

api = None

def init_pocket_option():
    global api
    try:
        if not PO_EMAIL or not PO_PASSWORD:
            logging.error("لم يتم العثور على PO_EMAIL أو PO_PASSWORD في متغيرات البيئة!")
            return False
        
        logging.info("جاري تسجيل الدخول إلى Pocket Option...")
        ssid = PocketOption.get_ssid_from_login(PO_EMAIL, PO_PASSWORD)
        if ssid:
            api = PocketOption(ssid)
            api.connect()
            logging.info("تم الاتصال بـ Pocket Option بنجاح!")
            return True
        else:
            logging.error("فشل الحصول على SSID عبر تسجيل الدخول.")
            return False
    except Exception as e:
        logging.error(f"خطأ أثناء تسجيل الدخول: {e}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("▶️ تشغيل البوت والتحليل", callback_data="start_bot")],
        [InlineKeyboardButton("📊 فحص الاتصال بالمنصة", callback_data="check_conn")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "أهلاً بك! بوت التداول الآلي جاهز للعمل بربط مباشر مع Pocket Option.",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    global api
    if query.data == "check_conn":
        if api and api.check_connect():
            await query.edit_message_text("✅ الاتصال شغال تمام والمنصة مرتبطة!")
        else:
            success = init_pocket_option()
            if success:
                await query.edit_message_text("✅ تم الاتصال بالمنصة بنجاح عبر البيانات المسجلة!")
            else:
                await query.edit_message_text("❌ فشل الاتصال بالمنصة. تحقق من الإيميل وكلمة المرور في Railway.")

    elif query.data == "start_bot":
        await query.edit_message_text("⏳ جاري فحص الشموع وتنفيذ الاستراتيجية...")
        if not api or not api.check_connect():
            init_pocket_option()

        if api:
            action, msg = check_signal_and_trade(api)
            await query.message.reply_text(f"النتيجة:\n{msg}")
        else:
            await query.message.reply_text("❌ البوت غير متصل بالمنصة حالياً.")

if __name__ == "__main__":
    # محاولة الاتصال عند تشغيل السيرفر
    init_pocket_option()

    # تشغيل بوت التلجرام
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("البوت يعمل الان...")
    app.run_polling()
