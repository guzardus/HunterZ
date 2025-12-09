import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Credentials
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

# Network Settings
# Default to True for safety, can be overridden by env var
BINANCE_TESTNET = os.getenv("BINANCE_TESTNET", "True").lower() in ("true", "1", "t")

# Trading Settings
TIMEFRAME = '30m'
RR_RATIO = 2.0
RISK_PER_TRADE = 1.0  # 1% of balance

# Symbol filtering
TRADING_PAIRS = [
    'BTC/USDT',
    'ETH/USDT',
    'SOL/USDT',
    'UNI/USDT',
    'DOT/USDT',
    'BNB/USDT'
]
