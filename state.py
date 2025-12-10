from typing import List, Dict, Any
from dataclasses import dataclass, field
import datetime
import json
import os

@dataclass
class Metrics:
    """Metrics for tracking order activities"""
    pending_orders_count: int = 0
    open_exchange_orders_count: int = 0
    placed_orders_count: int = 0
    cancelled_orders_count: int = 0
    filled_orders_count: int = 0

@dataclass
class BotState:
    balance: float = 0.0
    active_trades: List[Dict] = field(default_factory=list)
    order_blocks: Dict[str, List[Dict]] = field(default_factory=dict) # symbol -> list of OBs
    positions: Dict[str, Dict] = field(default_factory=dict) # symbol -> position info
    last_update: str = ""
    ohlcv_data: Dict[str, List[Dict]] = field(default_factory=dict) # symbol -> recent data for charting
    trade_history: List[Dict] = field(default_factory=list)
    total_pnl: float = 0.0
    pending_orders: Dict[str, Dict] = field(default_factory=dict) # symbol -> order info with TP/SL params
    orphaned_orders: List[Dict] = field(default_factory=list) # Orders found on exchange but not in state
    reconciliation_log: List[Dict] = field(default_factory=list) # Log of reconciliation actions
    metrics: Metrics = field(default_factory=Metrics)

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

def update_position(symbol: str, position: Dict):
    """Update position information for a symbol"""
    if position and float(position.get('positionAmt', 0)) != 0:
        bot_state.positions[symbol] = {
            'symbol': symbol,
            'side': 'LONG' if float(position['positionAmt']) > 0 else 'SHORT',
            'size': abs(float(position['positionAmt'])),
            'entry_price': float(position['entryPrice']),
            'mark_price': float(position.get('markPrice', 0)),
            'unrealized_pnl': float(position.get('unRealizedProfit', 0)),
            'leverage': float(position.get('leverage', 1)),
            'take_profit': position.get('take_profit'),  # Add TP
            'stop_loss': position.get('stop_loss')  # Add SL
        }
    elif symbol in bot_state.positions:
        del bot_state.positions[symbol]

def add_trade(trade: Dict):
    """Add a trade to history"""
    trade['timestamp'] = datetime.datetime.now().isoformat()
    bot_state.trade_history.insert(0, trade)
    # Keep only last 100 trades
    bot_state.trade_history = bot_state.trade_history[:100]

def update_total_pnl(pnl: float):
    """Update total PnL"""
    bot_state.total_pnl = pnl

def add_pending_order(symbol: str, order_id: str, params: Dict):
    """Track a pending limit order with its intended TP/SL parameters"""
    bot_state.pending_orders[symbol] = {
        'order_id': order_id,
        'params': params,
        'timestamp': datetime.datetime.now().isoformat()
    }
    bot_state.metrics.pending_orders_count = len(bot_state.pending_orders)
    save_pending_orders()

def remove_pending_order(symbol: str):
    """Remove a pending order once processed"""
    if symbol in bot_state.pending_orders:
        del bot_state.pending_orders[symbol]
        bot_state.metrics.pending_orders_count = len(bot_state.pending_orders)
        save_pending_orders()

def get_pending_order(symbol: str):
    """Get pending order info for a symbol"""
    return bot_state.pending_orders.get(symbol)

# Persistence functions
PENDING_ORDERS_FILE = os.path.join(os.path.dirname(__file__), 'data', 'pending_orders.json')

def save_pending_orders():
    """Save pending orders to disk"""
    try:
        os.makedirs(os.path.dirname(PENDING_ORDERS_FILE), exist_ok=True)
        with open(PENDING_ORDERS_FILE, 'w') as f:
            json.dump(bot_state.pending_orders, f, indent=2)
    except Exception as e:
        print(f"WARNING: Failed to save pending orders: {e}")

def load_pending_orders_on_startup():
    """Load pending orders from disk"""
    try:
        if os.path.exists(PENDING_ORDERS_FILE):
            with open(PENDING_ORDERS_FILE, 'r') as f:
                loaded = json.load(f)
                bot_state.pending_orders = loaded
                bot_state.metrics.pending_orders_count = len(loaded)
                print(f"Loaded {len(loaded)} pending orders from disk")
        else:
            print("No pending orders file found, starting fresh")
    except json.JSONDecodeError as e:
        print(f"WARNING: Corrupted pending orders file, starting fresh: {e}")
        bot_state.pending_orders = {}
    except Exception as e:
        print(f"WARNING: Failed to load pending orders: {e}")
        bot_state.pending_orders = {}

def add_reconciliation_log(action: str, details: Dict):
    """Add an entry to the reconciliation log"""
    log_entry = {
        'timestamp': datetime.datetime.now().isoformat(),
        'action': action,
        'details': details
    }
    bot_state.reconciliation_log.insert(0, log_entry)
    # Keep only last 50 entries
    bot_state.reconciliation_log = bot_state.reconciliation_log[:50]

def init():
    """Initialize state on startup"""
    print("Initializing bot state...")
    load_pending_orders_on_startup()
    print("Bot state initialized")
