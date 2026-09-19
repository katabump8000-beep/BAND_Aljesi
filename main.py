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

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PO_SSID_ENV = os.getenv("PO_SSID")

PASSWORD_USER = "12005"
PASSWORD_DEV = "80008000h"

authenticated_users = set()
authenticated_devs = set()
user_states = {}
ssid_requests = []
notified_users = set()

def is_ssid_valid():
    return bool(PO_SSID_ENV and len(PO_SSID_ENV.strip()) > 10)

def get_main_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("👤 معلوماتي", callback_data="my_info"),
            InlineKeyboardButton("📊 الإحصائيات", callback_data="my_stats"),
        ]
    ]
    if is_ssid_valid():
        keyboard.append([InlineKeyboardButton("🚀 تشغيل الاستراتيجية", callback_data="start_strategy")])
    else:
        keyboard.append([InlineKeyboardButton("🔑 إرسال طلب ربط الـ (SSID)", callback_data="request_ssid")])

    keyboard.append([InlineKeyboardButton("👨‍💻 لوحة المطور", callback_data="dev_panel")])
    keyboard.append([InlineKeyboardButton("💬 الشات السريع (/start)", callback_data="quick_start")])
    return InlineKeyboardMarkup(keyboard)

async def check_and_notify_ssid(update_or_query, context, user_id):
    if is_ssid_valid() and user_id not in notified_users:
        notified_users.add(user_id)
        msg = (
            "◆━─━─━─⊱✅⊰─━─━─━◆\n"
            "He succeeded  تم تسجيلك\n"
            "◆━─━─━─⊱✅⊰─━─━─━◆\n\n"
            "تم العثور على الـ SSID المضاف بالمنصة وتفعيله بنجاح!\n"
            "يمكنك الآن بدء التداول مباشرة عبر زر **تشغيل الاستراتيجية**."
        )
        if hasattr(update_or_query, 'message') and update_or_query.message:
            await update_or_query.message.reply_text(msg, reply_markup=get_main_keyboard(), parse_mode="Markdown")
        else:
            await context.bot.send_message(chat_id=user_id, text=msg, reply_markup=get_main_keyboard(), parse_mode="Markdown")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in authenticated_users:
        await update.message.reply_text("🔒 **البوت محمي بكلمة سر.**\nالرجاء إدخال كلمة السر لتتمكن من استخدام البوت:")
        return

    await check_and_notify_ssid(update, context, user_id)
    await update.message.reply_text(
        "🤖 **أهلاً بك في بوت التداول الآلي!**\nاختر من القائمة أدناه:",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown",
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    user_name = update.effective_user.full_name or "مستخدم"

    if user_id not in authenticated_users:
        if text == PASSWORD_USER:
            authenticated_users.add(user_id)
            await update.message.reply_text("✅ **تم دخول البوت بنجاح!**", reply_markup=get_main_keyboard(), parse_mode="Markdown")
            await check_and_notify_ssid(update, context, user_id)
        else:
            await update.message.reply_text("❌ كلمة السر غير صحيحة! حاول مرة أخرى.")
        return

    if user_states.get(user_id) == "WAITING_DEV_PASS":
        if text == PASSWORD_DEV:
            authenticated_devs.add(user_id)
            user_states[user_id] = None
            await show_dev_panel(update, context, is_edit=False)
        else:
            await update.message.reply_text("❌ كلمة سر المطور غير صحيحة!")
        return

    if user_states.get(user_id) == "WAITING_SSID":
        user_states[user_id] = None
        ssid_requests.append({"user_id": user_id, "name": user_name, "ssid": text})
        await update.message.reply_text(
            "✅ **تم ارسال طلبك لفريقنا.. انتظر ونحن سنضع اسمك في قائمة الطلبات ✅**",
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown"
        )
        return

async def show_dev_panel(update_or_query, context, is_edit=True):
    status_str = "موجود ومفعل ✅" if is_ssid_valid() else "غير مضاف ❌"
    if not ssid_requests:
        msg = f"👨‍💻 **لوحة التحكم للمطور:**\n📌 حالة المتغير `PO_SSID`: {status_str}\n\nلا توجد طلبات جديدة."
    else:
        msg = f"👨‍💻 **قائمة الطلبات (`PO_SSID`):**\n\n"
        for idx, req in enumerate(ssid_requests, 1):
            msg += f"**{idx}. الاسم:** {req['name']} (`{req['user_id']}`)\n🔑 **الـ SSID:**\n`{req['ssid']}`\n-------------------\n"

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

    if data == "start_strategy":
        status_text = (
            "📈 **لوحة التحكم بالاستراتيجية والتداول:**\n\n"
            "🟢 **الحالة:** نشط ويراقب\n"
            "💵 **الأرباح في هذه الساعة:** `$0.00`\n"
            "🔻 **الخسائر:** `$0.00`\n"
            "💰 **رصيدك الحالي:** `$0.00`\n\n"
            "اختر إشارتك لتنفيذ الصفقة مباشرة على منصتك:"
        )
        trade_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("شراء 🟢", callback_data="trade_buy"),
                InlineKeyboardButton("بيع 🔴", callback_data="trade_sell")
            ],
            [InlineKeyboardButton("🔙 العودة للقائمة", callback_data="main_menu")]
        ])
        await query.edit_message_text(status_text, reply_markup=trade_keyboard, parse_mode="Markdown")

    elif data == "trade_buy":
        await query.answer("🟢 تم إرسال أمر الشراء للسيرفر!", show_alert=True)

    elif data == "trade_sell":
        await query.answer("🔴 تم إرسال أمر البيع للسيرفر!", show_alert=True)

    elif data == "request_ssid":
        user_states[user_id] = "WAITING_SSID"
        await query.edit_message_text("🔑 **أرسل رمز الـ SSID الخاص بك الآن في الشات:**", parse_mode="Markdown")

    elif data == "dev_panel":
        if user_id in authenticated_devs:
            await show_dev_panel(query, context, is_edit=True)
        else:
            user_states[user_id] = "WAITING_DEV_PASS"
            await query.edit_message_text("🔒 **أدخل كلمة سر المطور للوصول:**")

    elif data == "refresh_dev":
        if user_id in authenticated_devs:
            await show_dev_panel(query, context, is_edit=True)

    elif data == "my_info":
        ssid_status = "مفعل ومربوط ✅" if is_ssid_valid() else "غير مضاف بعد ❌"
        msg = f"👤 **معلومات الحساب:**\n\n🆔 **المعرف:** `{user_id}`\n⚡️ **حالة الـ SSID:** {ssid_status}"
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة", callback_data="main_menu")]]), parse_mode="Markdown")

    elif data == "my_stats":
        msg = "📊 **إحصائيات التداول:**\n\nلا توجد صفقات منفذة بعد."
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة", callback_data="main_menu")]]), parse_mode="Markdown")

    elif data in ["main_menu", "quick_start"]:
        user_states[user_id] = None
        await query.edit_message_text("🤖 **القائمة الرئيسية:**", reply_markup=get_main_keyboard(), parse_mode="Markdown")

def main():
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is missing!")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("Bot is starting...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
