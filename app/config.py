import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
FLYER_API_KEY = os.getenv("FLYER_API_KEY")
FLYER_API_URL = os.getenv("FLYER_API_URL")
WITHDRAW_MIN_UNITS = int(os.getenv("WITHDRAW_MIN_UNITS", 60))
