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

# Reconciliation Settings
TP_SL_QUANTITY_TOLERANCE = 0.01  # 1% tolerance for quantity matching
POSITION_RECONCILIATION_INTERVAL = 600  # 10 minutes in seconds
def _safe_int_env(name, default):
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default

TP_SL_BUFFER_TICKS = _safe_int_env("TP_SL_BUFFER_TICKS", 1)
TP_SL_PENDING_BACKOFF_SECONDS = _safe_int_env("TP_SL_PENDING_BACKOFF_SECONDS", 60)
TP_SL_FALLBACK_MODE = os.getenv("TP_SL_FALLBACK_MODE", "MARKET_REDUCE")

# Active Position Monitoring
ENABLE_ACTIVE_TP_SL_MONITORING = True  # Set to False to rely only on Binance conditional orders
FORCED_CLOSURE_RATE_LIMIT_DELAY = 0.5  # Delay in seconds between forced closures to avoid rate limits
PENDING_ORDER_STALE_SECONDS = 900  # Cancel and replace pending orders older than 15 minutes

# Symbol filtering
# Note: MATIC/USDT and SHIB/USDT were removed as they are not available on Binance Testnet
TRADING_PAIRS = [
    'BTC/USDT',
    'ETH/USDT',
    'SOL/USDT',
    'UNI/USDT',
    'DOT/USDT',
    'BNB/USDT',
    'ADA/USDT',
    'LTC/USDT',
    'AVAX/USDT',
    'XRP/USDT',
    'DOGE/USDT',
]
