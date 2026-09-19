import os
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

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# كلمة سر البوت العامة وكلمة سر لوحة المطور
PASSWORD_USER = "12005"
PASSWORD_DEV = "80008000h"

# القوائم والمتغيرات المؤقتة في الذاكرة
authenticated_users = set()  # الأعضاء الموثوقون
authenticated_devs = set()   # المطورون الموثوقون
user_states = {}             # حالات المستخدمين

# قائمة طلبات الـ SSID المخزنة [(username/name, user_id, ssid)]
ssid_requests = []

def get_main_keyboard(user_id):
    """لوحة الأزرار الرئيسية"""
    keyboard = [
        [
            InlineKeyboardButton("👤 معلوماتي", callback_data="my_info"),
            InlineKeyboardButton("📊 الإحصائيات", callback_data="my_stats"),
        ],
        [InlineKeyboardButton("🔑 إرسال طلب ربط الـ (SSID)", callback_data="request_ssid")],
        [InlineKeyboardButton("👨‍💻 لوحة المطور", callback_data="dev_panel")],
        [InlineKeyboardButton("💬 الشات السريع (/start)", callback_data="quick_start")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in authenticated_users:
        await update.message.reply_text(
            "🔒 **البوت محمي بكلمة سر.**\n\nالرجاء إدخال كلمة السر لتتمكن من استخدام البوت:"
        )
        return

    await update.message.reply_text(
        "🤖 **أهلاً بك في بوت التداول الآلي!**\nاختر من القائمة أدناه:",
        reply_markup=get_main_keyboard(user_id),
        parse_mode="Markdown",
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    user_name = update.effective_user.full_name or update.effective_user.username or "مستخدم"

    # 1. الدخول العام للبوت
    if user_id not in authenticated_users:
        if text == PASSWORD_USER:
            authenticated_users.add(user_id)
            await update.message.reply_text(
                "✅ **تم دخول البوت بنجاح!**",
                reply_markup=get_main_keyboard(user_id),
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text("❌ كلمة السر غير صحيحة! حاول مرة أخرى.")
        return

    # 2. الدخول للوحة المطور بكلمة السر الخاصة
    if user_states.get(user_id) == "WAITING_DEV_PASS":
        if text == PASSWORD_DEV:
            authenticated_devs.add(user_id)
            user_states[user_id] = None
            await show_dev_panel(update, context, is_edit=False)
        else:
            await update.message.reply_text("❌ كلمة سر المطور غير صحيحة!")
        return

    # 3. استقبال رمز الـ SSID من العضو
    if user_states.get(user_id) == "WAITING_SSID":
        ssid_input = text
        user_states[user_id] = None
        
        # حفظ الطلب في القائمة
        ssid_requests.append({
            "user_id": user_id,
            "name": user_name,
            "ssid": ssid_input
        })
        
        await update.message.reply_text(
            "✅ **تم إرسال طلبك بنجاح!**\nانتظر ونحن سنضع اسمك في قائمة الطلبات وربط حسابك قريباً.",
            reply_markup=get_main_keyboard(user_id),
            parse_mode="Markdown"
        )
        return

async def show_dev_panel(update_or_query, context, is_edit=True):
    """عرض لوحة التحكم الخاصة بالمطور وقائمة الطلبات"""
    if not ssid_requests:
        msg = "👨‍💻 **لوحة التحكم للمطور:**\n\n📌 لا توجد أي طلبات SSID معلقة حالياً."
    else:
        msg = "👨‍💻 **قائمة طلبات الـ SSID المعلقة:**\n\n"
        for idx, req in enumerate(ssid_requests, 1):
            msg += f"**{idx}. المستخدم:** {req['name']} (`{req['user_id']}`)\n"
            msg += f"🔑 **الـ SSID:**\n`{req['ssid']}`\n"
            msg += "-----------------------------------\n"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 تحديث القائمة", callback_data="refresh_dev")],
        [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="main_menu")]
    ])

    if is_edit:
        await update_or_query.edit_message_text(msg, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await update_or_query.message.reply_text(msg, reply_markup=keyboard, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if user_id not in authenticated_users:
        await query.edit_message_text("🔒 **عذراً، يرجى إدخال كلمة السر أولاً.**")
        return

    data = query.data

    # طلب إضافة SSID
    if data == "request_ssid":
        user_states[user_id] = "WAITING_SSID"
        await query.edit_message_text(
            "🔑 **أرسل رمز الـ SSID الخاص بحسابك الآن في الشات:**\n\n"
            "سيتم تحويله تلقائياً لفريق التطوير لإضافته للربط.",
            parse_mode="Markdown"
        )

    # زر المطور
    elif data == "dev_panel":
        if user_id in authenticated_devs:
            await show_dev_panel(query, context, is_edit=True)
        else:
            user_states[user_id] = "WAITING_DEV_PASS"
            await query.edit_message_text(
                "🔒 **هذه المنطقة مخصصة للمطور فقط.**\n\nالرجاء كتابة كلمة سر المطور في الشات للوصول:"
            )

    # تحديث لوحة المطور
    elif data == "refresh_dev":
        if user_id in authenticated_devs:
            await show_dev_panel(query, context, is_edit=True)

    # معلومات المستخدم
    elif data == "my_info":
        user_name = query.from_user.full_name or "المستخدم"
        msg = (
            f"👤 **معلومات الحساب:**\n\n"
            f"🔹 **الاسم:** {user_name}\n"
            f"🆔 **معرف الحساب:** `{user_id}`\n"
            f"⚡️ **حالة الطلب:** يتم المراجعة من قبل المطور"
        )
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة للقائمة", callback_data="main_menu")]])
        await query.edit_message_text(msg, reply_markup=keyboard, parse_mode="Markdown")

    # الإحصائيات
    elif data == "my_stats":
        msg = "📊 **إحصائيات التداول:**\n\nلا توجد صفقات منفذة بعد."
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة للقائمة", callback_data="main_menu")]])
        await query.edit_message_text(msg, reply_markup=keyboard, parse_mode="Markdown")

    # العودة للقائمة الرئيسية
    elif data in ["main_menu", "quick_start"]:
        user_states[user_id] = None
        await query.edit_message_text(
            "🤖 **القائمة الرئيسية:**",
            reply_markup=get_main_keyboard(user_id),
            parse_mode="Markdown"
        )

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("Bot is running...")
    app.run_polling()
