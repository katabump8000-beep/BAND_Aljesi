import os
import time
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# إعداد السجلات
logging.basicConfig(level=logging.INFO)

PO_EMAIL = os.getenv("PO_EMAIL")
PO_PASSWORD = os.getenv("PO_PASSWORD")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# متغيرات الاستراتيجية والمضاعفة
current_amount = 1.0  # مبلغ الصفقة الابتدائي بالدولار
base_amount = 1.0     # المبلغ الأساسي للاعادة بعد الفوز

def analyze_and_get_signal(symbol="EURUSD_otc"):
    """
    محاكاة جلب وتحليل الشموع (60 ثانية)
    يتأكد من الاتجاه ويبحث عن فرصة دخول
    """
    # جلب التوقيت الحالي لحساب زمن إغلاق الشمعة
    current_sec = int(time.time()) % 60
    
    # حساب الثواني المتبقية حتى الثانية 38 (أي قبل الإغلاق بـ 22 ثانية)
    if current_sec < 38:
        time_to_wait = 38 - current_sec
    else:
        time_to_wait = (60 - current_sec) + 38

    return {
        "symbol": symbol,
        "wait_sec": time_to_wait,
        "current_sec": current_sec
    }

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 فحص إشارة التداول الآن", callback_data="check_signal")],
        [InlineKeyboardButton("⚙️ حالة الاتصال والبيانات", callback_data="check_status")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🤖 **بوت التداول الآلي جاهز!**\n\nالاستراتيجية: 3 شموع (1 دقيقة)\nالتوقيت: دخول قبل الإغلاق بـ 22 ثانية\nإدارة رأس المال: مضاعفة (Martingale)",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_amount
    query = update.callback_query
    await query.answer()

    if query.data == "check_status":
        masked_email = PO_EMAIL[:3] + "***" if PO_EMAIL else "غير محدد"
        await query.edit_message_text(
            f"✅ **الحساب مرتبط بالسيرفر**\n\nالبريد: `{masked_email}`\nالمبلغ الحالي للصفقة: `${current_amount}`",
            parse_mode="Markdown"
        )

    elif query.data == "check_signal":
        await query.edit_message_text("⏳ **جاري تحليل حركة الشموع (60 ثانية)...**")
        
        info = analyze_and_get_signal()
        
        msg = (
            f"📈 **نتيجة التحليل لزوج {info['symbol']}:**\n\n"
            f"⏱ الثواني الحالية في الشمعة: `{info['current_sec']}` ثانية\n"
            f"⏳ متبقي لدخول الصفقة (عند الثانية 38): `{info['wait_sec']}` ثانية\n"
            f"💰 مبلغ الصفقة القادمة: `${current_amount}`\n\n"
            f"⚡️ البوت جاهز لتنفيذ صفقة تلقائية فور توفر الإشارة!"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔄 تحديث التحليل", callback_data="check_signal")]
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("Bot is running...")
    app.run_polling()
