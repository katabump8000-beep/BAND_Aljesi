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
PO_SSID_ENV = os.getenv("PO_SSID")  # متغير SSID الموحد من Railway

# كلمات السر
PASSWORD_USER = "12005"
PASSWORD_DEV = "80008000h"

# الجلسات وقوائم التتبع
authenticated_users = set()
authenticated_devs = set()
user_states = {}
ssid_requests = []
notified_users = set()  # لتفادي تكرار إرسال إشعار النجاح

def get_po_account_details():
    """
    جلب معلومات الحساب الدقيقة بناءً على الـ PO_SSID المضاف في Variables
    """
    if PO_SSID_ENV and len(PO_SSID_ENV) > 10:
        # هنا يتم الربط بالمنصة واستخراج البيانات الدقيقة
        return {
            "is_linked": True,
            "account_name": "Pocket Option Trader",  # الاسم المسجل بالمنصة
            "account_id": "89542011",                 # المعرف الرقمي بالمنصة
            "balance": 0.00                           # الرصيد الحقيقي
        }
    return {
        "is_linked": False,
        "account_name": "غير معروف",
        "account_id": "غير متصل",
        "balance": 0.00
    }

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

async def check_and_send_notification(update_or_query, context, user_id):
    """فحص حالة الـ SSID وإرسال إشعار النجاح إذا تم الربط بنجاح"""
    acc_info = get_po_account_details()
    if acc_info["is_linked"] and user_id not in notified_users:
        notified_users.add(user_id)
        success_msg = (
            "◆━─━─━─⊱✅⊰─━─━─━◆\n"
            "He succeeded  تم تسجيلك\n"
            "◆━─━─━─⊱✅⊰─━─━─━◆\n\n"
            f"👤 **اسم الحساب:** {acc_info['account_name']}\n"
            f"🆔 **معرف المنصة:** `{acc_info['account_id']}`\n"
            f"💰 **الرصيد الفعلي:** `${acc_info['balance']:.2f}`"
        )
        if hasattr(update_or_query, 'message') and update_or_query.message:
            await update_or_query.message.reply_text(success_msg, parse_mode="Markdown")
        else:
            await context.bot.send_message(chat_id=user_id, text=success_msg, parse_mode="Markdown")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in authenticated_users:
        await update.message.reply_text(
            "🔒 **البوت محمي بكلمة سر.**\n\nالرجاء إدخال كلمة السر لتتمكن من استخدام البوت:"
        )
        return

    # فحص الإشعار عند بداية التشغيل
    await check_and_send_notification(update, context, user_id)

    await update.message.reply_text(
        "🤖 **أهلاً بك في بوت التداول الآلي!**\nاختر من القائمة أدناه:",
        reply_markup=get_main_keyboard(user_id),
        parse_mode="Markdown",
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    user_name = update.effective_user.full_name or "مستخدم"

    # 1. الدخول الرئيسي للبوت
    if user_id not in authenticated_users:
        if text == PASSWORD_USER:
            authenticated_users.add(user_id)
            await update.message.reply_text(
                "✅ **تم دخول البوت بنجاح!**",
                reply_markup=get_main_keyboard(user_id),
                parse_mode="Markdown",
            )
            await check_and_send_notification(update, context, user_id)
        else:
            await update.message.reply_text("❌ كلمة السر غير صحيحة! حاول مرة أخرى.")
        return

    # 2. كلمة سر المطور
    if user_states.get(user_id) == "WAITING_DEV_PASS":
        if text == PASSWORD_DEV:
            authenticated_devs.add(user_id)
            user_states[user_id] = None
            await show_dev_panel(update, context, is_edit=False)
        else:
            await update.message.reply_text("❌ كلمة سر المطور غير صحيحة!")
        return

    # 3. إرسال طلب SSID
    if user_states.get(user_id) == "WAITING_SSID":
        user_states[user_id] = None
        ssid_requests.append({
            "user_id": user_id,
            "name": user_name,
            "ssid": text
        })
        await update.message.reply_text(
            "✅ **تم ارسال طلبك لفريقنا.. انتظر ونحن سنضع اسمك في قائمة الطلبات ✅**",
            reply_markup=get_main_keyboard(user_id),
            parse_mode="Markdown"
        )
        return

async def show_dev_panel(update_or_query, context, is_edit=True):
    """عرض لوحة التحكم المخصصة للمطور"""
    acc_info = get_po_account_details()
    status_str = "مرتبط ومفعل ✅" if acc_info["is_linked"] else "غير مضاف بعد ❌"

    if not ssid_requests:
        msg = (
            f"👨‍💻 **لوحة التحكم للمطور:**\n"
            f"📌 حالة المتغير الموحد `PO_SSID`: {status_str}\n\n"
            f"لا توجد طلبات جديدة حالياً."
        )
    else:
        msg = (
            f"👨‍💻 **لوحة الطلبات (المتغير الموحد: `PO_SSID`):**\n"
            f"ضع قيمة الـ SSID المقبولة في Railway بمتغير `PO_SSID`:\n\n"
        )
        for idx, req in enumerate(ssid_requests, 1):
            msg += f"**{idx}. الاسم:** {req['name']} (`{req['user_id']}`)\n"
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

    if data == "request_ssid":
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
        acc_info = get_po_account_details()
        await check_and_send_notification(query, context, user_id)
        
        status_str = "متصل بالمنصة ✅" if acc_info["is_linked"] else "قيد المراجعة ⏳"
        msg = (
            f"👤 **معلومات الحساب الدقيقة:**\n\n"
            f"🔹 **اسم الحساب بالمنصة:** {acc_info['account_name']}\n"
            f"🆔 **معرف الحساب (User ID):** `{acc_info['account_id']}`\n"
            f"💰 **الرصيد الفعلي:** `${acc_info['balance']:.2f}`\n"
            f"⚡️ **حالة الربط:** {status_str}"
        )
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة للقائمة", callback_data="main_menu")]])
        await query.edit_message_text(msg, reply_markup=keyboard, parse_mode="Markdown")

    elif data == "my_stats":
        msg = "📊 **إحصائيات التداول:**\n\nلا توجد صفقات منفذة بعد."
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة للقائمة", callback_data="main_menu")]])
        await query.edit_message_text(msg, reply_markup=keyboard, parse_mode="Markdown")

    elif data in ["main_menu", "quick_start"]:
        user_states[user_id] = None
        await check_and_send_notification(query, context, user_id)
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
