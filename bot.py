import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
import database as db

# ⚠️ التوكن - الأفضل تحطه في Railway Variables باسم TELEGRAM_BOT_TOKEN
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# ============ حالات المستخدمين ============
# state: main_password | admin_password | waiting_delete_username | waiting_new_password | waiting_confirm_kick
user_states = {}

# ============ نصوص مزخرفة ============
MSG_ASK_PASSWORD = (
    "◆━─━─━─⊱🔑⊰─━─━─━◆\n"
    "رجاءا قم بإدخال كلمة المرور:\n"
    "◆━─━─━─⊱🔒⊰─━─━─━◆"
)

MSG_WRONG_PASSWORD = (
    "◆━─━─━─⊱❌⊰─━─━─━◆\n"
    "خطأ. كلمة المرور غير صحيحة\n"
    "◆━─━─━─⊱⛔⊰─━─━─━◆"
)

MSG_BLOCKED = (
    "◆━─━─━─━⊱⚠️⊰━─━─━─━◆\n"
    "عذرا انت محظور من التسجيل لمدة 5د\n"
    "◆━─━─━─━⊱⚠️⊰━─━─━─━◆"
)

MSG_MAIN_MENU = (
    "◆━─━─━─⊱✅⊰─━─━─━◆\n"
    "تم التحقق بنجاح!\n"
    "اختر من القائمة:\n"
    "◆━─━─━─⊱🔓⊰─━─━─━◆"
)

MSG_ASK_ADMIN_PASSWORD = (
    "◆━─━─━─⊱🔐⊰─━─━─━◆\n"
    "رجاءا قم بإدخال كلمة سر الصيانة:\n"
    "◆━─━─━─⊱🔒⊰─━─━─━◆"
)

MSG_ADMIN_MENU = (
    "◆━─━─━─⊱🛠️⊰─━─━─━◆\n"
    "لوحة الصيانة\n"
    "اختر العملية:\n"
    "◆━─━─━─⊱⚙️⊰─━─━─━◆"
)

MSG_ASK_DELETE_NAME = (
    "◆━─━─━─⊱🗑️⊰─━─━─━◆\n"
    "يرجى كتابة اسم المستخدم بالدقة التامة وإرساله:\n"
    "◆━─━─━─⊱✍️⊰─━─━─━◆"
)

MSG_ASK_NEW_PASSWORD = (
    "❆━━━━━═⏣⊰🔒⊱⏣═━━━━━❆\n"
    "رجاءا ارسل كلمة المرور الجديدة:\n"
    "❆━━━━━═⏣⊰🔑⊱⏣═━━━━━❆"
)

MSG_PASSWORD_RESET = (
    "❉▬▬▬▬▬▬▬▬▬❉\n"
    "تم إعادة ضبط كلمة المرور\n"
    "✥▬▬▬▬▬▬▬▬▬✥"
)

MSG_CONFIRM_KICK = "هل تريد طرد كل المتسخدمين من جديد؟"


# ============ الأزرار ============
def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔧 صيانة", callback_data="maintenance")],
    ])

def admin_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 عرض المستخدمين", callback_data="list_users")],
        [InlineKeyboardButton("🗑️ حذف", callback_data="delete_user")],
        [InlineKeyboardButton("🔵 تغيير كلمة المرور", callback_data="change_password")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="back_main")],
    ])

def delete_confirm_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ رجوع", callback_data="back_admin")],
    ])

def yes_no_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ نعم", callback_data="kick_yes"),
            InlineKeyboardButton("❌ لا", callback_data="kick_no"),
        ],
    ])

def back_only_keyboard(target="back_admin"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ رجوع", callback_data=target)],
    ])


# ============ الأوامر ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if db.is_blocked(user_id):
        await update.message.reply_text(MSG_BLOCKED)
        return
    
    user_states[user_id] = "main_password"
    await update.message.reply_text(MSG_ASK_PASSWORD)


# ============ معالج الرسائل النصية ============
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    text = update.message.text.strip()
    
    # إذا محظور
    if db.is_blocked(user_id):
        await update.message.reply_text(MSG_BLOCKED)
        return
    
    state = user_states.get(user_id)
    
    # ===== إدخال كلمة السر الرئيسية =====
    if state == "main_password" or state is None:
        correct = db.get_setting("main_password")
        if text == correct:
            db.reset_attempts(user_id)
            db.register_user(user_id, user.username or "", user.first_name or "")
            user_states[user_id] = "logged_in"
            await update.message.reply_text(
                MSG_MAIN_MENU,
                reply_markup=main_menu_keyboard(),
            )
        else:
            count = db.increment_attempts(user_id)
            if count >= 5:
                db.block_user(user_id, 5)
                db.reset_attempts(user_id)
                user_states.pop(user_id, None)
                await update.message.reply_text(MSG_BLOCKED)
            else:
                await update.message.reply_text(MSG_WRONG_PASSWORD)
        return
    
    # ===== إدخال كلمة سر الصيانة =====
    if state == "admin_password":
        correct = db.get_setting("admin_password")
        if text == correct:
            user_states[user_id] = "admin_menu"
            await update.message.reply_text(
                MSG_ADMIN_MENU,
                reply_markup=admin_menu_keyboard(),
            )
        else:
            await update.message.reply_text(MSG_WRONG_PASSWORD)
        return
    
    # ===== انتظار اسم المستخدم للحذف =====
    if state == "waiting_delete_username":
        target = db.get_user_by_username(text)
        if not target:
            await update.message.reply_text(
                "❌ لم يتم العثور على مستخدم بهذا الاسم.\n"
                "تأكد من الاسم بالدقة التامة.",
                reply_markup=delete_confirm_keyboard(),
            )
            return
        target_id, target_username, target_name = target
        db.delete_user(target_id)
        # نرسل إشعار للمطرود لو أمكن
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text="⛔ تم طردك من البوت. يرجى إعادة إدخال كلمة المرور.",
            )
        except Exception:
            pass
        user_states[target_id] = None
        user_states[user_id] = "admin_menu"
        await update.message.reply_text(
            f"✅ تم طرد المستخدم: @{target_username or target_name}",
            reply_markup=admin_menu_keyboard(),
        )
        return
    
    # ===== انتظار كلمة المرور الجديدة =====
    if state == "waiting_new_password":
        db.set_setting("main_password", text)
        user_states[user_id] = "waiting_kick_confirm"
        await update.message.reply_text(
            MSG_PASSWORD_RESET,
            reply_markup=yes_no_keyboard(),
        )
        await update.message.reply_text(MSG_CONFIRM_KICK, reply_markup=yes_no_keyboard())
        return
    
    # ===== في أي حالة تانية =====
    await update.message.reply_text("استخدم /start للبدء.")


# ============ معالج الأزرار ============
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    
    # زر صيانة
    if data == "maintenance":
        user_states[user_id] = "admin_password"
        await query.edit_message_text(MSG_ASK_ADMIN_PASSWORD)
        return
    
    # رجوع للقائمة الرئيسية
    if data == "back_main":
        user_states[user_id] = "logged_in"
        await query.edit_message_text(MSG_MAIN_MENU, reply_markup=main_menu_keyboard())
        return
    
    # رجوع للوحة الإدارة
    if data == "back_admin":
        user_states[user_id] = "admin_menu"
        await query.edit_message_text(MSG_ADMIN_MENU, reply_markup=admin_menu_keyboard())
        return
    
    # عرض المستخدمين
    if data == "list_users":
        users = db.get_all_users()
        if not users:
            text = "📋 لا يوجد مستخدمون مسجلون بعد."
        else:
            lines = ["📋 قائمة المستخدمين المسجلين:\n"]
            for i, (uid, uname, fname, reg) in enumerate(users, 1):
                lines.append(f"{i}. {fname} | @{uname or 'بدون'} | ID: {uid}")
            text = "\n".join(lines)
        await query.edit_message_text(text, reply_markup=back_only_keyboard("back_admin"))
        return
    
    # حذف مستخدم
    if data == "delete_user":
        user_states[user_id] = "waiting_delete_username"
        await query.edit_message_text(MSG_ASK_DELETE_NAME, reply_markup=delete_confirm_keyboard())
        return
    
    # تغيير كلمة المرور
    if data == "change_password":
        user_states[user_id] = "waiting_new_password"
        await query.edit_message_text(MSG_ASK_NEW_PASSWORD, reply_markup=back_only_keyboard("back_admin"))
        return
    
    # تأكيد الطرد (yes/no)
    if data == "kick_yes":
        db.delete_all_users()
        # نطرد كل المستخدمين من الحالة
        for uid in list(user_states.keys()):
            if uid != user_id:
                user_states[uid] = None
        user_states[user_id] = "admin_menu"
        await query.edit_message_text(
            "✅ تم طرد جميع المستخدمين. سيطلب من الجميع كلمة المرور من جديد.",
            reply_markup=admin_menu_keyboard(),
        )
        return
    
    if data == "kick_no":
        user_states[user_id] = "admin_menu"
        await query.edit_message_text(
            "✅ تم تغيير كلمة المرور فقط.",
            reply_markup=admin_menu_keyboard(),
        )
        return


# ============ التشغيل ============
def main():
    db.init_db()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Meliora bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()