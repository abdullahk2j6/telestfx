import logging
import asyncio
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta, timezone
from ta.momentum import RSIIndicator
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Telegram Setup ---
TELEGRAM_TOKEN = '7642544760:AAEUFuTKBoQHh8jNIkgMwF--WLutmGt7pzM'
CHAT_ID = '5906456335'
bot = Bot(token=TELEGRAM_TOKEN)

# --- Forex Pairs ---
PAIRS = {
    'EURUSD': 'EURUSD=X',
    'GBPJPY': 'GBPJPY=X',
    'USDTRY': 'USDTRY=X',
    'AUDJPY': 'AUDJPY=X',
    'NZDJPY': 'NZDJPY=X',
    'EURJPY': 'EURJPY=X',
    'GBPUSD': 'GBPUSD=X',
    'USDZAR': 'USDZAR=X',
    'USDSEK': 'USDSEK=X',
    'EURGBP': 'EURGBP=X',
    'USDCAD': 'USDCAD=X',
    'CHFJPY': 'CHFJPY=X',
    'AUDUSD': 'AUDUSD=X',
    'USDCHF': 'USDCHF=X',
    'EURCHF': 'EURCHF=X',
    'NZDUSD': 'NZDUSD=X',
    'USDMXN': 'USDMXN=X',
    'GBPAUD': 'GBPAUD=X'
}

# --- Timeframes ---
TIMEFRAMES = {
    '15m': '15m',
    '1h': '60m',
    '4h': '4h',
    '1d': '1d'
}

# --- Active Signal Cache ---
active_signals = {}

# --- RSI Crossover Signal ---
def get_rsi_crossover_signal(df: pd.DataFrame) -> str:
    if df.shape[0] < 101:
        return "❌"

    close_series = df['Close'].squeeze()
    rsi_25 = RSIIndicator(close=close_series, window=25).rsi()
    rsi_100 = RSIIndicator(close=close_series, window=100).rsi()

    prev_25 = rsi_25.iloc[-2]
    prev_100 = rsi_100.iloc[-2]
    curr_25 = rsi_25.iloc[-1]
    curr_100 = rsi_100.iloc[-1]

    if prev_25 < prev_100 and curr_25 > curr_100:
        return "✅"
    elif prev_25 > prev_100 and curr_25 < curr_100:
        return "✅"
    else:
        return "❌"

# --- Historical Crossovers (Last 4 Days) ---
def get_historical_crossovers(df: pd.DataFrame) -> list[str]:
    close_series = df['Close'].squeeze()
    rsi_25 = RSIIndicator(close=close_series, window=25).rsi()
    rsi_100 = RSIIndicator(close=close_series, window=100).rsi()
    crossovers = []
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=4)

    for i in range(1, len(df)):
        if i < 100:
            continue

        prev_25 = rsi_25.iloc[i - 1]
        prev_100 = rsi_100.iloc[i - 1]
        curr_25 = rsi_25.iloc[i]
        curr_100 = rsi_100.iloc[i]

        if pd.isna(prev_25) or pd.isna(prev_100) or pd.isna(curr_25) or pd.isna(curr_100):
            continue

        timestamp = df.index[i]
        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize('UTC')
        if timestamp < cutoff_time:
            continue

        timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M')
        if prev_25 < prev_100 and curr_25 > curr_100:
            crossovers.append(f"✅ Buy  — {timestamp_str}")
        elif prev_25 > prev_100 and curr_25 < curr_100:
            crossovers.append(f"❌ Sell — {timestamp_str}")

    return crossovers

# --- Bot Analysis + Alerts ---
async def analyze_and_alert():
    global active_signals
    for pair_name, ticker in PAIRS.items():
        msg = f"<b>📊 Pair: {pair_name}</b>\n"
        signal_detected = False

        for tf_label, tf_code in TIMEFRAMES.items():
            try:
                df = yf.download(tickers=ticker, period='7d', interval=tf_code)
                if df.empty:
                    msg += f"<code>{tf_label.upper():<4} → ❌</code>\n"
                    continue

                emoji = get_rsi_crossover_signal(df)
                key = f"{pair_name}_{tf_label}"

                if emoji == "✅":
                    if active_signals.get(key) != "✅":
                        msg += f"<code>{tf_label.upper():<4} → ✅</code>\n"
                        active_signals[key] = "✅"
                        signal_detected = True
                    else:
                        msg += f"<code>{tf_label.upper():<4} → ❌</code>\n"
                else:
                    msg += f"<code>{tf_label.upper():<4} → ❌</code>\n"
                    if active_signals.get(key) == "✅":
                        active_signals[key] = "❌"

            except Exception as e:
                logger.error(f"Error fetching data for {pair_name} ({tf_label}): {e}")

        if signal_detected:
            await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="HTML")

# --- Background Loop ---
async def main_loop():
    await bot.send_message(chat_id=CHAT_ID, text="🚀 Bot started.")
    while True:
        try:
            await analyze_and_alert()
        except Exception as e:
            logger.error(f"Main loop error: {e}")
        await asyncio.sleep(300)

# --- Telegram Commands ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Running!")

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏓 Pong! Bot is working.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ I'm monitoring the signals as soon as I get something I will update you.")

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📖 Fetching history (last 4 days)...")
    try:
        for pair_name, ticker in PAIRS.items():
            for tf_label, tf_code in TIMEFRAMES.items():
                try:
                    df = yf.download(tickers=ticker, period='7d', interval=tf_code)
                    if df.empty:
                        continue
                    crossovers = get_historical_crossovers(df)
                    if crossovers:
                        header = f"<b>📈 {pair_name} — {tf_label.upper()}</b>\n" + "─" * 25
                        msg = header + "\n" + "\n".join(crossovers)
                        await update.message.reply_text(msg, parse_mode="HTML")
                except Exception as e:
                    logger.error(f"Error fetching history for {pair_name} ({tf_label}): {e}")
    except Exception as e:
        await update.message.reply_text("❌ Error while fetching history.")
        logger.error(f"History command error: {e}")

# --- Manual Signal Check Command ---
async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active_signals
    active_signals.clear()
    await update.message.reply_text("📡 Checking crossover signals...")
    try:
        await analyze_and_alert()
        await update.message.reply_text("✅ Signal check complete.")
    except Exception as e:
        await update.message.reply_text("❌ Error during signal check.")
        logger.error(f"Signal command error: {e}")

# --- Run Bot ---
def run_bot():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("signal", signal))

    loop = asyncio.get_event_loop()
    loop.create_task(main_loop())
    app.run_polling()

if __name__ == "__main__":
    run_bot()
