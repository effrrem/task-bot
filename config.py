import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise ValueError(
        "BOT_TOKEN не задан. Скопируй .env.example в .env и впиши токен из @BotFather."
    )

REMIND_MINUTES_BEFORE = int(os.getenv("REMIND_MINUTES_BEFORE", "10"))