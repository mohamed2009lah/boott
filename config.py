import os

TOKEN = os.getenv("BOT_TOKEN")

ADMIN_IDS = [
    int(x) for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
]

API_KEY = os.getenv("SHRINKEARN_API_KEY", "")
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN", "")

REFERRAL_POINTS = int(os.getenv("REFERRAL_POINTS", "5"))
DAILY_BONUS_POINTS = int(os.getenv("DAILY_BONUS_POINTS", "2"))
MIN_WITHDRAW = float(os.getenv("MIN_WITHDRAW", "2.0"))

if not TOKEN:
    raise RuntimeError("BOT_TOKEN missing")