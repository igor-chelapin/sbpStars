import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "").split(",") if id]
STARS_RATE = float(os.getenv("STARS_RATE", 1.5))
BOT_COMMISSION = float(os.getenv("BOT_COMMISSION", 0.05))