from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')
SCRAPE_DELAY = int(os.getenv('SCRAPE_DELAY_SECONDS', 2))
MAX_RETRIES = int(os.getenv('MAX_RETRIES', 3))

USER_AGENT = os.getenv('USER_AGENT', 'Mozilla/5.0 (compatible; WebScraperBot/1.0)')
PLAYWRIGHT_HEADLESS = os.getenv('PLAYWRIGHT_HEADLESS', 'true').lower() == 'true'

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_DIR = os.getenv('LOG_DIR', 'logs')

WEBHOOK_URL = os.getenv('WEBHOOK_URL')

# LLM Keys
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
