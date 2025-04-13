import json
from datetime import datetime, timedelta, timezone

import pandas as pd
import yfinance as yf
from ta.momentum import RSIIndicator
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse

from telegram import Update, Bot
from telegram.ext import (
    Application, CommandHandler, ContextTypes
)

# Telegram Bot Settings
TELEGRAM_TOKEN = '7642544760:AAEUFuTKBoQHh8jNIkgMwF--WLutmGt7pzM'  # Replace with your actual token
CHAT_ID = '5906456335'  # Replace with your actual chat ID
bot = Bot(token=TELEGRAM_TOKEN)
application = Application.builder().token(TELEGRAM_TOKEN).build()

# Forex pairs and timeframes
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

TIMEFRAMES = {
    '15m': '15m',
    '1h': '60m',
    '4h': '4h',
    '1d': '1d'
}

active_signals = {}

# --- Signal Logic ---
def get_rsi_crossover_signal(df: pd.DataFrame) -> str:
    if df.shape[0] < 101:
        return "❌"
    close_series = df['Close'].squeeze()
    rsi_25 = RSIIndicator(close=close_series, window=25).rsi()
    rsi_100 = RSIIndicator(close=close_series, window=100).rsi()
    prev_25, prev_100 = rsi_25.iloc[-2], rsi_100.iloc[-2]
    curr_25, curr_100 = rsi_25.iloc[-1], rsi_100.iloc[-1]
    if prev_25 < prev_100 and curr_25 > curr_100:
        return "✅"
    elif prev_25 > prev_100 and curr_25 < curr_100:
        return "✅"
    return "❌"

def get_historical_crossovers(df: pd.DataFrame) -> list[str]:
    close_series = df['Close'].squeeze()
    rsi_25 = RSIIndicator(close=close_series, window=25).rsi()
    rsi_100 = RSIIndicator(close=close_series, window=100).rsi()
    crossovers = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=4)
    for i in range(1, len(df)):
        if i < 100: continue
        prev_25, prev_100 = rsi_25.iloc[i-1], rsi_100.iloc[i-1]
        curr_25, curr_100 = rsi_25.iloc[i], rsi_100.iloc[i]
        if pd.isna(prev_25) or pd.isna(prev_100) or pd.isna(curr_25) or pd.isna(curr_100):
            continue
        timestamp = df.index[i]
        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize('UTC')
        if timestamp < cutoff:
            continue
        ts_str = timestamp.strftime('%Y-%m-%d %H:%M')
        if prev_25 < prev_100 and curr_25 > curr_100:
            crossovers.append(f"✅ Buy  — {ts_str}")
        elif prev_25 > prev_100 and curr_25 < curr_100:
            crossovers.append(f"❌ Sell — {ts_str}")
    return crossovers

# --- Commands ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hello! Bot is alive and running via Django!")

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏓 Pong! The bot is responsive.")

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📖 Fetching crossover history (last 4 days)...")
    try:
        for pair_name, ticker in PAIRS.items():
            for tf_label, tf_code in TIMEFRAMES.items():
                df = yf.download(ticker, period='7d', interval=tf_code)
                if df.empty: continue
                crossovers = get_historical_crossovers(df)
                if crossovers:
                    header = f"<b>📈 {pair_name} — {tf_label.upper()}</b>\n" + "─" * 25
                    msg = header + "\n" + "\n".join(crossovers)
                    await update.message.reply_text(msg, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text("❌ Error fetching history.")
        print("History error:", e)

async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active_signals
    active_signals.clear()
    await update.message.reply_text("📡 Checking live RSI signals...")
    try:
        for pair_name, ticker in PAIRS.items():
            msg = f"<b>📊 Pair: {pair_name}</b>\n"
            for tf_label, tf_code in TIMEFRAMES.items():
                df = yf.download(ticker, period='7d', interval=tf_code)
                if df.empty:
                    msg += f"<code>{tf_label.upper():<4} → ❌</code>\n"
                    continue
                emoji = get_rsi_crossover_signal(df)
                key = f"{pair_name}_{tf_label}"
                if emoji == "✅":
                    if active_signals.get(key) != "✅":
                        msg += f"<code>{tf_label.upper():<4} → ✅</code>\n"
                        active_signals[key] = "✅"
                    else:
                        msg += f"<code>{tf_label.upper():<4} → ❌</code>\n"
                else:
                    msg += f"<code>{tf_label.upper():<4} → ❌</code>\n"
                    active_signals[key] = "❌"
            await update.message.reply_text(msg, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text("❌ Error during signal check.")
        print("Signal error:", e)

# Register all command handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("ping", ping))
application.add_handler(CommandHandler("history", history))
application.add_handler(CommandHandler("signal", signal))

# --- Webhook view ---
@csrf_exempt
def telegram_webhook(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
            update = Update.de_json(data, bot)
            application.update_queue.put_nowait(update)
        except Exception as e:
            print("Webhook error:", e)
        return JsonResponse({"status": "ok"})
    return HttpResponse("Hello from Django Telegram Bot!")
