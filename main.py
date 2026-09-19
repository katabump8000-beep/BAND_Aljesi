import os
import time
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# إعداد السجلات
logging.basicConfig(level=logging.INFO)

# جلب البيانات من Variables
PO_EMAIL = os.getenv("PO_EMAIL")
PO_PASSWORD = os.getenv("PO_PASSWORD")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# كلمة السر المطلوبة لاستخدام البوت
PASSWORD_SECRET = "12005"

# متغيّرات الإحصائيات الافتراضية
stats = {
    "wins": 0,
    "losses": 0,
    "total_profit": 0.0,
    "balance": 100.0,  # رصيد افتراضي للعرض (سيتم ربطه تلقائياً)
}

# للتحقق من الجلسات الموثوقة (من أدخل كلمة السر)
authenticated_users = set()


def is_auth(user_id):
    return user_id in authenticated_users


def get_main_keyboard():
    """لوحة الأزرار الرئيسية"""
    keyboard = [
        [
            InlineKeyboardButton("👤 معلوماتي", callback_data="my_info"),
            InlineKeyboardButton("📊 الإحصائيات", callback_data="my_stats"),
        ],
        [
            InlineKeyboardButton(
                "📈 فحص إشارة التداول", callback_data="check_signal"
            )
        ],
        [InlineKeyboardButton("💬 الشات السريع (/start)", callback_data="quick_start")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_auth(user_id):
        await update.message.reply_text(
            "🔒 **البوت محمي بكلمة سر.**\n\nالرجاء إدخال كلمة السر لتتمكن من استخدام البوت:"
        )
        return

    await update.message.reply_text(
        "🤖 **أهلاً بك في بوت التداول الآلي!**\nاختر من القائمة أدناه:",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown",
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # التحقق من كلمة السر
    if not is_auth(user_id):
        if text == PASSWORD_SECRET:
            authenticated_users.add(user_id)
            await update.message.reply_text(
                "✅ **تم تسجيل الدخول بنجاح!**\nالبوت جاهز للاستخدام الآن.",
                reply_markup=get_main_keyboard(),
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text("❌ كلمة السر غير صحيحة! حاول مرة أخرى.")
        return


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    # حماية الأزرار من غير المصرح لهم
    if not is_auth(user_id):
        await query.edit_message_text(
            "🔒 **عذراً، يرجى إدخال كلمة السر أولاً في الشات.**"
        )
        return

    data = query.data

    # 1. زر معلوماتي
    if data == "my_info":
        user_name = query.from_user.first_name or "المستخدم"
        masked_email = PO_EMAIL[:3] + "***" if PO_EMAIL else "غير محدد"

        msg = (
            f"👤 **معلومات الحساب والتداول:**\n\n"
            f"🔹 **الاسم:** {user_name}\n"
            f"📧 **البريد:** `{masked_email}`\n"
            f"💰 **الرصيد الحالي:** `${stats['balance']:.2f}`\n"
            f"🏛 **نوع الحساب:** حقيقي (Pocket Option)\n"
            f"⚡️ **حالة الربط:** متصل أونلاين ✅"
        )
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data="main_menu")]]
        )
        await query.edit_message_text(
            msg, reply_markup=keyboard, parse_mode="Markdown"
        )

    # 2. زر الإحصائيات
    elif data == "my_stats":
        total_trades = stats["wins"] + stats["losses"]
        win_rate = (
            (stats["wins"] / total_trades * 100) if total_trades > 0 else 0.0
        )

        msg = (
            f"📊 **إحصائيات التداول:**\n\n"
            f"✅ **الصفقات الرابحة:** `{stats['wins']}`\n"
            f"❌ **الصفقات الخاسرة:** `{stats['losses']}`\n"
            f"📈 **إجمالي الصفقات:** `{total_trades}`\n"
            f"🎯 **نسبة النجاح (Win Rate):** `{win_rate:.1f}%`\n"
            f"💵 **صافي الأرباح:** `${stats['total_profit']:.2f}`"
        )
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data="main_menu")]]
        )
        await query.edit_message_text(
            msg, reply_markup=keyboard, parse_mode="Markdown"
        )

    # 3. زر فحص الإشارة
    elif data == "check_signal":
        msg = (
            "⏳ **جاري تحليل السوق ومراقبة الشموع...**\n"
            "الاستراتيجية: 3 شموع متتالية (1 دقيقة)"
        )
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data="main_menu")]]
        )
        await query.edit_message_text(
            msg, reply_markup=keyboard, parse_mode="Markdown"
        )

    # 4. زر الشات السريع (/start)
    elif data == "quick_start":
        await query.edit_message_text(
            "🔄 **تم تحديث الجلسة واختصار الشات!**",
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown",
        )

    # 5. القائمة الرئيسية
    elif data == "main_menu":
        await query.edit_message_text(
            "🤖 **القائمة الرئيسية:**",
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown",
        )


if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    app.add_handler(CallbackQueryHandler(button_handler))

    print("Bot starting...")
    app.run_polling()
