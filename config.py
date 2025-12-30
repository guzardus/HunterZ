import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Credentials for Hyperliquid
WALLET_ADDRESS = os.getenv("HYPERLIQUID_WALLET_ADDRESS")
PRIVATE_KEY = os.getenv("HYPERLIQUID_PRIVATE_KEY")

# Trading Settings
TIMEFRAME = '30m'
RR_RATIO = 2.0
RISK_PER_TRADE = 1.0  # 1% of balance

# Reconciliation Settings
TP_SL_QUANTITY_TOLERANCE = 0.01  # 1% tolerance for quantity matching
POSITION_RECONCILIATION_INTERVAL = 600  # 10 minutes in seconds
PENDING_ORDER_STALE_SECONDS = 3600  # 1 hour - pending orders older than this are considered stale
TP_SL_PLACEMENT_COOLDOWN_SECONDS = 30  # Seconds to wait after placing TP/SL before trying again (API sync delay)

# Active Position Monitoring
ENABLE_ACTIVE_TP_SL_MONITORING = True  # Set to False to rely only on Hyperliquid conditional orders
FORCED_CLOSURE_RATE_LIMIT_DELAY = 0.5  # Delay in seconds between forced closures to avoid rate limits

# Symbol filtering - Using USDC pairs for Hyperliquid
TRADING_PAIRS = [
    'BTC/USDC:USDC',
    'ETH/USDC:USDC',
    'SOL/USDC:USDC'
]
