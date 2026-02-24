import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.environ["BOT_TOKEN"]
DOWNLOADS_DIR: str = os.getenv("DOWNLOADS_DIR", "downloads")
MAX_FILE_SIZE_BYTES: int = int(os.getenv("MAX_FILE_SIZE_MB", "50")) * 1024 * 1024
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

TELEGRAM_FILE_LIMIT_BYTES: int = 50 * 1024 * 1024
