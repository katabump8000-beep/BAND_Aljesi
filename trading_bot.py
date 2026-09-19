import os
import time
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════
# ⚙️ الإعدادات (من Railway Variables)
# ═══════════════════════════════════════
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
SSID = os.environ.get("POCKET_OPTION_SSID", "")

# ═══════════════════════════════════════
# 🎛️ إعدادات الاستراتيجية
# ═══════════════════════════════════════
CONFIG = {
    "candle_count": 3,
    "entry_lead_seconds": 22,
    "initial_amount": 1.0,
    "martingale_multiplier": 2.0,
    "max_martingale_steps": 3,
    "asset": "EURUSD_otc",
    "trade_duration": 60,
    "candle_period": 60,
}

# ═══════════════════════════════════════
# 🤖 حالة البوت
# ═══════════════════════════════════════
class TradingState:
    def __init__(self):
        self.running = False
        self.connected = False
        self.balance = 0.0
        self.candle_history = []
        self.martingale_step = 0
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
        self.pnl = 0.0
        self.last_signal = None
        self.task = None
        self.status_msg = "في الانتظار"

state = TradingState()

# ═══════════════════════════════════════
# 📊 منطق الاستراتيجية
# ═══════════════════════════════════════
def get_candle_color(candle):
    return "green" if candle["close"] > candle["open"] else "red"

def calculate_amount():
    if state.martingale_step >= CONFIG["max_martingale_steps"]:
        return None
    return CONFIG["initial_amount"] * (CONFIG["martingale_multiplier"] ** state.martingale_step)

def seconds_to_candle_close():
    now = time.time()
    period = CONFIG["candle_period"]
    candle_open = now - (now % period)
    candle_close = candle_open + period
    return candle_close - now

async def trading_loop():
    """حلقة التداول الرئيسية"""
    logger.info("🚀 بدء حلقة التداول...")
    state.status_msg = "جاري الاتصال..."
    
    try:
        from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync
        
        async with PocketOptionAsync(SSID) as client:
            state.connected = True
            state.balance = await client.balance()
            state.status_msg = "متصل - في انتظار إشارة"
            logger.info(f"✅ متصل! الرصيد: ${state.balance}")
            
            async for candle in client.subscribe_symbol(CONFIG["asset"]):
                if not state.running:
                    break
                if "time" not in candle:
                    continue
                
                state.candle_history.append(candle)
                if len(state.candle_history) > 50:
                    state.candle_history.pop(0)
                
                if len(state.candle_history) < CONFIG["candle_count"]:
                    continue
                
                last_n = state.candle_history[-CONFIG["candle_count"]:]
                colors = [get_candle_color(c) for c in last_n]
                
                signal = None
                if all(c == "green" for c in colors):
                    signal = "call"
                elif all(c == "red" for c in colors):
                    signal = "put"
                
                if not signal:
                    continue
                
                state.last_signal = signal
                state.status_msg = f"إشارة {signal.upper()} - في انتظار التوقيت"
                logger.info(f"🎯 إشارة: {signal.upper()}")
                
                while state.running:
                    secs = seconds_to_candle_close()
                    if secs <= CONFIG["entry_lead_seconds"] and secs > 0:
                        break
                    await asyncio.sleep(0.5)
                
                if not state.running:
                    break
                
                amount = calculate_amount()
                if amount is None:
                    logger.warning("⛔ وصلنا للحد الأقصى. إعادة تعيين Martingale.")
                    state.martingale_step = 0
                    continue
                
                try:
                    state.status_msg = f"فتح صفقة {signal.upper()} بـ ${amount}"
                    trade_id, _ = await client.buy(
                        CONFIG["asset"], amount, CONFIG["trade_duration"],
                        action=signal,
                    )
                    state.total_trades += 1
                    logger.info(f"✅ صفقة #{state.total_trades} | {signal} | ${amount}")
                    
                    state.status_msg = "في انتظار نتيجة الصفقة"
                    result = await client.check_win(trade_id)
                    
                    if result == "win":
                        state.wins += 1
                        state.martingale_step = 0
                        state.pnl += amount * 0.92
                        logger.info("✅ ربح")
                    else:
                        state.losses += 1
                        state.martingale_step += 1
                        state.pnl -= amount
                        logger.info(f"❌ خسارة | Martingale: {state.martingale_step}")
                    
                    state.balance = await client.balance()
                    state.status_msg = "في انتظار إشارة"
                except Exception as e:
                    logger.error(f"خطأ في الصفقة: {e}")
                    state.status_msg = f"خطأ: {e}"
    
    except Exception as e:
        logger.error(f"خطأ في الاتصال: {e}")
        state.status_msg = f"خطأ اتصال: {e}"
    finally:
        state.connected = False
        state.running = False
        state.status_msg = "متوقف"
        logger.info("🛑 توقف حلقة التداول")

# ═══════════════════════════════════════
# 🎨 واجهة تيليجرام
# ═══════════════════════════════════════
def dashboard_keyboard():
    if state.running:
        main_btn = InlineKeyboardButton("⏹️ إيقاف البوت", callback_data="stop_bot")
    else:
        main_btn = InlineKeyboardButton("▶️ تشغيل البوت", callback_data="start_bot")
    
    return InlineKeyboardMarkup([
        [main_btn],
        [InlineKeyboardButton("🔄 تحديث", callback_data="refresh")],
        [InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings")],
    ])

def dashboard_text():
    status = "🟢 شغال" if state.running else "🔴 متوقف"
    conn = "✅ متصل" if state.connected else "❌ غير متصل"
    
    return (
        "╔═══════════════════════════╗\n"
        "║  🤖 MELIORA TRADING BOT   ║\n"
        "╚═══════════════════════════╝\n\n"
        f"📡 الحالة: {status}\n"
        f"🔗 الاتصال: {conn}\n"
        f"📋 العملية: {state.status_msg}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 الرصيد: ${state.balance:.2f}\n"
        f"📈 الربح/الخسارة: ${state.pnl:+.2f}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 إجمالي الصفقات: {state.total_trades}\n"
        f"✅ ربح: {state.wins}  |  ❌ خسارة: {state.losses}\n"
        f"🔄 Martingale: خطوة {state.martingale_step}\n"
        f"🎯 آخر إشارة: {state.last_signal or '—'}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"⚙️ {CONFIG['candle_count']} شموع | دخول قبل {CONFIG['entry_lead_seconds']}ث\n"
        f"💵 ${CONFIG['initial_amount']} | مضاعف x{CONFIG['martingale_multiplier']}"
    )

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(dashboard_text(), reply_markup=dashboard_keyboard())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "start_bot":
        if not state.running:
            state.running = True
            state.task = asyncio.create_task(trading_loop())
        await query.edit_message_text(dashboard_text(), reply_markup=dashboard_keyboard())
    
    elif data == "stop_bot":
        state.running = False
        await query.edit_message_text(dashboard_text(), reply_markup=dashboard_keyboard())
    
    elif data == "refresh":
        await query.edit_message_text(dashboard_text(), reply_markup=dashboard_keyboard())
    
    elif data == "settings":
        await query.edit_message_text(
            "⚙️ **إعدادات الاستراتيجية**\n\n"
            f"• عدد الشموع المتتالية: `{CONFIG['candle_count']}`\n"
            f"• الدخول قبل: `{CONFIG['entry_lead_seconds']}` ثانية\n"
            f"• المبلغ الأولي: `${CONFIG['initial_amount']}`\n"
            f"• مضاعف Martingale: `x{CONFIG['martingale_multiplier']}`\n"
            f"• أقصى خطوات: `{CONFIG['max_martingale_steps']}`\n"
            f"• الأصل: `{CONFIG['asset']}`\n"
            f"• مدة الصفقة: `{CONFIG['trade_duration']}ث`\n\n"
            "_لتعديل القيم، عدّل ملف trading_bot.py في GitHub_",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ رجوع", callback_data="refresh")],
            ]),
        )

# ═══════════════════════════════════════
# ▶️ التشغيل
# ═══════════════════════════════════════
def main():
    if not BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN غير موجود!")
        return
    if not SSID:
        print("❌ POCKET_OPTION_SSID غير موجود!")
        return
    
    logger.info("🤖 بدء بوت التداول...")
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("✅ Trading bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()