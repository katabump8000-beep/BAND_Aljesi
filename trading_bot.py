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
    """أخضر إذا close > open، أحمر إذا close < open"""
    o = candle.get("open") or candle.get("o") or 0
    c = candle.get("close") or candle.get("c") or 0
    return "green" if c > o else "red"

def calculate_amount():
    """حساب المبلغ حسب Martingale"""
    if state.martingale_step >= CONFIG["max_martingale_steps"]:
        return None
    return CONFIG["initial_amount"] * (CONFIG["martingale_multiplier"] ** state.martingale_step)

def seconds_to_candle_close():
    """الثواني المتبقية لإغلاق الشمعة الحالية"""
    now = time.time()
    period = CONFIG["candle_period"]
    candle_open = now - (now % period)
    candle_close = candle_open + period
    return candle_close - now

# ═══════════════════════════════════════
# 🔄 حلقة التداول
# ═══════════════════════════════════════
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
            
            last_candle_time = None
            
            while state.running:
                try:
                    # جلب آخر 10 شموع
                    candles = await client.get_candles(
                        CONFIG["asset"],
                        CONFIG["candle_period"],
                        10,
                    )
                    
                    if not candles or len(candles) < CONFIG["candle_count"] + 1:
                        await asyncio.sleep(3)
                        continue
                    
                    # نتجاهل الشمعة الحالية (غير مغلقة) وناخذ المغلقة فقط
                    closed_candles = candles[:-1]
                    
                    if len(closed_candles) < CONFIG["candle_count"]:
                        await asyncio.sleep(3)
                        continue
                    
                    # آخر N شموع مغلقة
                    last_n = closed_candles[-CONFIG["candle_count"]:]
                    
                    # نتحقق من آخر شمعة مغلقة (لتجنب التكرار)
                    last_closed_time = last_n[-1].get("time") or last_n[-1].get("timestamp")
                    
                    if last_closed_time == last_candle_time:
                        await asyncio.sleep(2)
                        continue
                    
                    # ألوان الشموع
                    colors = [get_candle_color(c) for c in last_n]
                    
                    signal = None
                    if all(c == "green" for c in colors):
                        signal = "call"
                    elif all(c == "red" for c in colors):
                        signal = "put"
                    
                    if not signal:
                        last_candle_time = last_closed_time
                        await asyncio.sleep(2)
                        continue
                    
                    # ═══ إشارة تحققت ═══
                    last_candle_time = last_closed_time
                    state.last_signal = signal
                    state.status_msg = f"إشارة {signal.upper()} - في انتظار التوقيت"
                    logger.info(f"🎯 إشارة: {signal.upper()}")
                    
                    # ننتظر لين ندخل النافذة الزمنية
                    waited = 0
                    while state.running:
                        secs = seconds_to_candle_close()
                        
                        # إذا الشمعة الحالية قربت تخلص، ننتظر شمعة جديدة
                        if secs <= CONFIG["entry_lead_seconds"] and secs > 0:
                            break
                        await asyncio.sleep(0.5)
                        waited += 0.5
                        if waited > 60:
                            # إذا مرت دقيقة وما دخلنا النافذة، نلغي
                            break
                    
                    if not state.running:
                        break
                    
                    amount = calculate_amount()
                    if amount is None:
                        logger.warning("⛔ وصلنا للحد الأقصى. إعادة تعيين Martingale.")
                        state.martingale_step = 0
                        continue
                    
                    # ═══ تنفيذ الصفقة ═══
                    state.status_msg = f"فتح صفقة {signal.upper()} بـ ${amount}"
                    logger.info(f"💰 فتح صفقة: {signal} | ${amount}")
                    
                    try:
                        trade_id, _ = await client.buy(
                            CONFIG["asset"],
                            amount,
                            CONFIG["trade_duration"],
                            action=signal,
                        )
                        state.total_trades += 1
                        logger.info(f"✅ صفقة #{state.total_trades} | ID: {trade_id}")
                        
                        state.status_msg = "في انتظار نتيجة الصفقة"
                        result = await client.check_win(trade_id)
                        logger.info(f"📊 النتيجة: {result}")
                        
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
                    except Exception as trade_err:
                        logger.error(f"❌ خطأ في الصفقة: {trade_err}")
                        state.status_msg = f"خطأ صفقة: {trade_err}"
                
                except Exception as loop_err:
                    logger.error(f"⚠️ خطأ في الحلقة: {loop_err}")
                    state.status_msg = f"خطأ: {loop_err}"
                    await asyncio.sleep(5)
    
    except Exception as e:
        logger.error(f"❌ خطأ في الاتصال: {e}")
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
