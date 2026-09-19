import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from strategy import StrategyConfig

config = StrategyConfig(
    candle_count=3,
    entry_seconds_before_close=22
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 بوت التداول التجريبي يعمل\n\n"
        f"📊 عدد الشموع: {config.candle_count}\n"
        f"⏱️ الدخول قبل الإغلاق: {config.entry_seconds_before_close} ثانية\n\n"
        "الحالة: 🟢 يعمل"
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📊 حالة البوت\n\n"
        "🟢 النظام: يعمل\n"
        f"🕯️ الشموع المطلوبة: {config.candle_count}\n"
        f"⏱️ توقيت الدخول: قبل الإغلاق بـ {config.entry_seconds_before_close} ثانية\n"
        "💰 الوضع: تجريبي"
    )


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")

    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN غير موجود")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))

    print("Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()