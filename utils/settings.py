import os
from dotenv import load_dotenv


class BaseSettings:
    """Loads and stores configuration parameters from environment variables."""

    LOGGING_FILENAME: str = "project.log"

    def __init__(self):
        """Initializes default configuration attributes."""
        self.TOKEN = None
        self.SUPABASE_URL = None
        self.SUPABASE_KEY = None
        self.CHANNEL_ID = None
        self.MY_TELEGRAM_ID = None
        self.PROXY_URL = None

    def load_from_dotenv(self) -> None:
        """Reads environment variables from the .env file."""
        load_dotenv()

        self.TOKEN = os.getenv("TOKEN")
        self.SUPABASE_URL = os.getenv("SUPABASE_URL")
        self.SUPABASE_KEY = os.getenv("SUPABASE_KEY")
        self.CHANNEL_ID = os.getenv("CHANNEL_ID")
        self.PROXY_URL = os.getenv("PROXY_URL")

        my_id = os.getenv("MY_TELEGRAM_ID")
        self.MY_TELEGRAM_ID = int(my_id) if my_id and my_id.isdigit() else None


settings = BaseSettings()
