from typing import List, Dict, Any
from dataclasses import dataclass, field
import datetime

@dataclass
class BotState:
    balance: float = 0.0
    active_trades: List[Dict] = field(default_factory=list)
    order_blocks: Dict[str, List[Dict]] = field(default_factory=dict) # symbol -> list of OBs
    last_update: str = ""
    ohlcv_data: Dict[str, List[Dict]] = field(default_factory=dict) # symbol -> recent data for charting

# Global instance
bot_state = BotState()

def update_balance(balance: float):
    bot_state.balance = balance
    bot_state.last_update = datetime.datetime.now().isoformat()

def update_order_blocks(symbol: str, obs: List[Dict]):
    # Convert timestamps to string if needed or keep as is
    # For JSON serialization in API, we might need strings
    bot_state.order_blocks[symbol] = obs

def update_ohlcv(symbol: str, df):
    # Keep last 100 candles for chart
    # df is a DataFrame with DatetimeIndex
    records = []
    # We need to make sure we serialize correctly. 
    # Lightweight charts expects: { time: '2018-12-22', open: 75.16, high: 82.84, low: 36.16, close: 45.72 }
    # Time can be unix timestamp.
    for index, row in df.tail(100).iterrows():
        records.append({
            'time': int(index.timestamp()), # Unix timestamp
            'open': row['open'],
            'high': row['high'],
            'low': row['low'],
            'close': row['close'],
        })
    bot_state.ohlcv_data[symbol] = records
