"""Conversational AI Agent — a REAL AI you talk to, not a command bot.

Kemi is an autonomous offensive security AI agent accessible via Telegram.
She understands natural language, remembers context, has a personality,
and autonomously decides when to scan, chat, or explain.	"""
import asyncio, json, os, re
from datetime import datetime
from collections import defaultdict

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# Conversation memory per chat
_conversations = defaultdict(list)
MAX_HISTORY = 20

_active_agents = {}

KEMI_SOUL = "االام الامد قاميم "؂مي Kemi” ✓ وكلفه امن ال AI محركاوانلام القانيم اجلاريم. كاماصنم العرياعا المسبسالعياعن. احلان الاو الميركاوانلام!"
