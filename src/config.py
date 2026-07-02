import os
from dotenv import load_dotenv

load_dotenv()

APP_ENV = os.getenv("APP_ENV", "dev")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "20"))
USER_AGENT = os.getenv("USER_AGENT", "Mozilla/5.0")