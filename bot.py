import os
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from strategy import (
    StrategyConfig,
    get_signal,
    get_entry_time,
    is_entry_time,
    next_amount,
)


config = StrategyConfig(
    candle_count=3,
    entry_seconds_before_close=22,
    base_amount=1.0,
    multiplier=2.0,
)


BOT_STATUS = "🟢 يعمل"
CURRENT_AMOUNT = config.base_amount
LAST_SIGNAL = "لا توجد"
LAST_RESULT = "لا توجد"
TRADE_COUNT = 0


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 بوت التداول التجريبي\n\n"
        f"الحالة: {BOT_STATUS}\n"
        f"🕯️ الشموع: {config.candle_count}\n"
        f"⏱️ الدخول قبل الإغلاق: "
        f"{config.entry_seconds_before_close} ثانية\n"
        f"💵 المبلغ الأساسي: ${config.base_amount:.2f}\n"
        f"📈 المضاعف: {config.multiplier}x\n\n"
        "الأوامر:\n"
        "/status - حالة البوت\n"
        "/demo - اختبار الاستراتيجية\n"
        "/config - الإعدادات"
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📊 Dashboard\n\n"
        f"الحالة: {BOT_STATUS}\n"
        f"🕯️ عدد الشموع: {config.candle_count}\n"
        f"⏱️ التوقيت: قبل الإغلاق بـ "
        f"{config.entry_seconds_before_close} ثانية\n"
        f"💵 المبلغ الحالي: ${CURRENT_AMOUNT:.2f}\n"
        f"📈 المضاعف: {config.multiplier}x\n"
        f"📡 آخر إشارة: {LAST_SIGNAL}\n"
        f"📋 آخر نتيجة: {LAST_RESULT}\n"
        f"🔢 عدد الاختبارات: {TRADE_COUNT}"
    )


async def config_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚙️ إعدادات الاستراتيجية\n\n"
        f"عدد الشموع = {config.candle_count}\n"
        f"قبل الإغلاق = {config.entry_seconds_before_close} ثانية\n"
        f"المبلغ الأساسي = ${config.base_amount:.2f}\n"
        f"المضاعف = {config.multiplier}x"
    )


async def demo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global LAST_SIGNAL
    global LAST_RESULT
    global TRADE_COUNT
    global CURRENT_AMOUNT

    candles = [
        {"open": 100, "close": 101},
        {"open": 101, "close": 103},
        {"open": 103, "close": 105},
    ]

    signal = get_signal(candles, config)

    TRADE_COUNT += 1

    if signal:
        LAST_SIGNAL = signal

        if signal == "CALL":
            signal_text = "🟢 CALL"
        else:
            signal_text = "🔴 PUT"

        LAST_RESULT = "محاكاة فقط"

        await update.message.reply_text(
            "🧪 اختبار الاستراتيجية\n\n"
            f"الشموع الأخيرة: {config.candle_count}\n"
            f"الإشارة: {signal_text}\n"
            f"المبلغ التجريبي: ${CURRENT_AMOUNT:.2f}\n"
            f"الحالة: محاكاة فقط\n\n"
            "⚠️ لم يتم تنفيذ أي صفقة حقيقية."
        )

    else:
        LAST_SIGNAL = "لا توجد"
        LAST_RESULT = "لا توجد إشارة"

        await update.message.reply_text(
            "🧪 اختبار الاستراتيجية\n\n"
            "⚪ لا توجد إشارة."
        )


async def timer_demo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    candle_close = datetime.now() + timedelta(seconds=60)

    entry = get_entry_time(candle_close, config)

    await update.message.reply_text(
        "⏱️ اختبار المؤقت\n\n"
        f"إغلاق الشمعة: {candle_close.strftime('%H:%M:%S')}\n"
        f"وقت الدخول المحسوب: {entry.strftime('%H:%M:%S')}\n"
        f"الفارق: {config.entry_seconds_before_close} ثانية\n\n"
        "🧪 الاختبار محاكاة فقط."
    )


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN غير موجود في Railway Variables"
        )

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("config", config_command))
    app.add_handler(CommandHandler("demo", demo))
    app.add_handler(CommandHandler("timer", timer_demo))

    print("Trading bot started.")

    app.run_polling()


if __name__ == "__main__":
    main()
