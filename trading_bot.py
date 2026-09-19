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

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
SSID = os.environ.get("POCKET_OPTION_SSID", "")

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

class TradingState:
    def __init__(self):
        self.running = False
        self.connected = False
        self.balance = 0.0
        self.martingale_step = 0
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
        self.pnl = 0.0
        self.last_signal = None
        self.task = None
        self.status_msg = "في الانتظار"
        self.current_candle = None

state = TradingState()

def calculate_amount():
    if state.martingale_step >= CONFIG["max_martingale_steps"]:
        return None
    return CONFIG["initial_amount"] * (CONFIG["martingale_multiplier"] ** state.martingale_step)

def get_color(open_price, close_price):
    return "green" if close_price > open_price else "red"

def seconds_to_candle_close():
    now = time.time()
    period = CONFIG["candle_period"]
    candle_open = now - (now % period)
    candle_close = candle_open + period
    return candle_close - now

async def trading_loop():
    logger.info("🚀 بدء حلقة التداول...")
    state.status_msg = "جاري الاتصال..."
    
    try:
        from BinaryOptionsToolsV2 import PocketOptionAsync
        
        async with PocketOptionAsync(ssid=SSID) as client:
            state.connected = True
            state.balance = await client.balance()
            state.status_msg = "متصل - في انتظار إشارة"
            logger.info(f"✅ متصل! الرصيد: ${state.balance}")
            
            last_processed_candle_time = None
            
            # استخدام get_candles_live - الطريقة الرسمية
            async for closed_candles, forming_candle in client.get_candles_live(
                CONFIG["asset"],
                period=CONFIG["candle_period"],
                hours=2.0,
                max_rows=100,
            ):
                if not state.running:
                    break
                
                try:
                    # خزّن الشمعة الحالية
                    state.current_candle = forming_candle
                    
                    # نتحقق من الإشارة على الشموع المغلقة + الشمعة الحالية
                    if len(closed_candles) < CONFIG["candle_count"]:
                        continue
                    
                    # آخر (candle_count - 1) شمعة مغلقة + الشمعة الحالية
                    needed_closed = CONFIG["candle_count"] - 1
                    last_closed = closed_candles[-needed_closed:] if needed_closed > 0 else []
                    
                    # فحص لون الشموع
                    closed_colors = [
                        get_color(c.get("open", c.get("o", 0)), c.get("close", c.get("c", 0)))
                        for c in last_closed
                    ]
                    
                    forming_color = None
                    if forming_candle:
                        forming_color = get_color(
                            forming_candle.get("open", forming_candle.get("o", 0)),
                            forming_candle.get("close", forming_candle.get("c", 0)),
                        )
                    
                    # الإشارة: كل الشموع المغلقة + الشمعة الحالية بنفس اللون
                    all_colors = closed_colors + ([forming_color] if forming_color else [])
                    
                    signal = None
                    if len(all_colors) >= CONFIG["candle_count"]:
                        if all(c == "green" for c in all_colors[-CONFIG["candle_count"]:]):
                            signal = "call"
                        elif all(c == "red" for c in all_colors[-CONFIG["candle_count"]]):
                            signal = "put"
                    
                    if not signal:
                        await asyncio.sleep(1)
                        continue
                    
                    # نجيب وقت الشمعة الحالية عشان نتجنب التكرار
                    current_candle_time = None
                    if forming_candle:
                        current_candle_time = forming_candle.get("time") or forming_candle.get("timestamp")
                    
                    if current_candle_time == last_processed_candle_time:
                        await asyncio.sleep(1)
                        continue
                    
                    # ═══ إشارة تحققت ═══
                    state.last_signal = signal
                    state.status_msg = f"إشارة {signal.upper()} - في انتظار التوقيت"
                    logger.info(f"🎯 إشارة: {signal.upper()} | الشمعة الحالية: {forming_color}")
                    
                    # ═══ ننتظر التوقيت المناسب ═══
                    # ننتظر لين نصل للنافذة الزمنية (قبل 22 ثانية من إغلاق الشمعة)
                    waited = 0
                    while state.running and waited < 55:
                        secs = seconds_to_candle_close()
                        if secs <= CONFIG["entry_lead_seconds"] and secs > 0:
                            break
                        await asyncio.sleep(0.5)
                        waited += 0.5
                    
                    if not state.running:
                        break
                    
                    last_processed_candle_time = current_candle_time
                    
                    # ═══ تنفيذ الصفقة ═══
                    amount = calculate_amount()
                    if amount is None:
                        logger.warning("⛔ وصلنا للحد الأقصى من Martingale. إعادة تعيين.")
                        state.martingale_step = 0
                        continue
                    
                    state.status_msg = f"فتح صفقة {signal.upper()} بـ ${amount}"
                    logger.info(f"💰 فتح صفقة: {signal} | ${amount}")
                    
                    try:
                        trade_id, _ = await client.buy(
                            CONFIG["asset"],
                            amount,
                            CONFIG["trade_duration"],
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
                    except Exception as e:
                        logger.error(f"❌ خطأ في الصفقة: {e}")
                        state.status_msg = f"خطأ: {e}"
                
                except Exception as e:
                    logger.error(f"⚠️ خطأ في الحلقة: {e}")
                    await asyncio.sleep(2)
    
    except Exception as e:
        logger.error(f"❌ خطأ في الاتصال: {e}")
        state.status_msg = f"خطأ اتصال: {e}"
    finally:
        state.connected = False
        state.running = False
        state.status_msg = "متوقف"
        logger.info("🛑 توقف حلقة التداول")

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
            f"• عدد الشموع: `{CONFIG['candle_count']}`\n"
            f"• الدخول قبل: `{CONFIG['entry_lead_seconds']}` ثانية\n"
            f"• المبلغ الأولي: `${CONFIG['initial_amount']}`\n"
            f"• مضاعف Martingale: `x{CONFIG['martingale_multiplier']}`\n"
            f"• أقصى خطوات: `{CONFIG['max_martingale_steps']}`\n"
            f"• الأصل: `{CONFIG['asset']}`\n"
            f"• مدة الصفقة: `{CONFIG['trade_duration']}ث`",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ رجوع", callback_data="refresh")],
            ]),
        )

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
