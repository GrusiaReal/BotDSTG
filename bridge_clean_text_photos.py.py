# bridge_clean_text_photos.py
# requirements: python -m pip install discord.py requests

from dotenv import load_dotenv
import os

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

import re
import sys
import time
import asyncio
import requests
import mimetypes
from concurrent.futures import ThreadPoolExecutor
import discord
from discord import Intents

# ── ЗАПОЛНИ СВОИ ДАННЫЕ (вставь НОВЫЕ токены!) ─────────────────────
import os
from dotenv import load_dotenv
load_dotenv()  # загрузит .env из текущей папки

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
DISCORD_CHANNEL_IDS = [int(x) for x in os.getenv("DISCORD_CHANNEL_IDS", "").split(",") if x.strip()]

# ───────────────────────────────────────────────────────────────────

# Быстрая валидация входных
DISCORD_CHANNEL_IDS = [int(x) for x in DISCORD_CHANNEL_IDS]
TELEGRAM_CHAT_ID = str(TELEGRAM_CHAT_ID).strip()  # на всякий случай уберём скрытые пробелы/табы

if not DISCORD_TOKEN or not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID or not DISCORD_CHANNEL_IDS:
    raise SystemExit("❌ Заполните DISCORD_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, DISCORD_CHANNEL_IDS.")

# Для корректного asyncio на Windows
if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

TG_API_BASE = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# ---------- Фильтрация текста ----------
def clean_message(text: str) -> str:
    text = re.sub(r'@\S+', '', text)          # убрать @... (в т.ч. @everyone)
    text = text.replace('||', '').replace('>', '')
    return text.strip()

def is_image_name_or_url(name_or_url: str) -> bool:
    kind, _ = mimetypes.guess_type(name_or_url)
    return (kind or "").startswith("image/")

# ---------- СИНХРОННЫЕ функции (в потоках) ----------
def _tg_send_text_sync(chat_id: str, text: str):
    if not text.strip():
        return
    try:
        r = requests.post(f"{TG_API_BASE}/sendMessage",
                          data={"chat_id": chat_id, "text": text},
                          timeout=30)
        if r.status_code != 200:
            print("[TG sendMessage] ❌", r.status_code, r.text[:300])
        if r.status_code == 429:
            retry = int(r.json().get("parameters", {}).get("retry_after", 1))
            time.sleep(retry)
            _tg_send_text_sync(chat_id, text)
    except Exception as e:
        print("Telegram sendMessage error:", e)

def _tg_send_photo_by_url_sync(chat_id: str, url: str, caption: str = ""):
    try:
        r = requests.post(f"{TG_API_BASE}/sendPhoto",
                          data={"chat_id": chat_id, "photo": url, "caption": caption},
                          timeout=60)
        if r.status_code != 200:
            print("[TG sendPhoto] ❌", r.status_code, r.text[:300])
        if r.status_code == 429:
            retry = int(r.json().get("parameters", {}).get("retry_after", 1))
            time.sleep(retry)
            _tg_send_photo_by_url_sync(chat_id, url, caption)
    except Exception as e:
        print("Telegram sendPhoto error:", e)

# ---------- ASYNC-обёртки ----------
_executor = ThreadPoolExecutor(max_workers=4)

async def tg_send_text(text: str):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(_executor, _tg_send_text_sync, TELEGRAM_CHAT_ID, text)

async def tg_send_photo_by_url(url: str, caption: str = ""):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(_executor, _tg_send_photo_by_url_sync, TELEGRAM_CHAT_ID, url, caption)

# ---------- Discord клиент ----------
intents = Intents.default()
intents.message_content = True  # включи Message Content Intent в Dev Portal
bot = discord.Client(intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}. Listening channels: {DISCORD_CHANNEL_IDS}")

@bot.event
async def on_message(message: discord.Message):
    try:
        if message.author.bot:
            return
        if message.channel.id not in DISCORD_CHANNEL_IDS:
            return

        # Текст
        if message.content:
            cleaned = clean_message(message.content)
            if cleaned:
                await tg_send_text(cleaned)

        # Фото
        for a in message.attachments:
            is_img = (a.content_type or "").startswith("image/") or is_image_name_or_url(a.filename or a.url)
            if is_img:
                await tg_send_photo_by_url(a.url, caption="")

    except Exception as e:
        print(f"[on_message error] {type(e).__name__}: {e}")

@bot.event
async def on_error(event_method, *args, **kwargs):
    print(f"[on_error] in {event_method}", args, kwargs)

if __name__ == "__main__":
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        print(f"[run error] {type(e).__name__}: {e}")
