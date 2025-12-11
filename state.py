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
    total_balance: float = 0.0  # Total balance including used margin
    free_balance: float = 0.0   # Available balance for trading
    active_trades: List[Dict] = field(default_factory=list)
    order_blocks: Dict[str, List[Dict]] = field(default_factory=dict) # symbol -> list of OBs
    positions: Dict[str, Dict] = field(default_factory=dict) # symbol -> position info
    last_update: str = ""
    ohlcv_data: Dict[str, List[Dict]] = field(default_factory=dict) # symbol -> recent data for charting
    trade_history: List[Dict] = field(default_factory=list)
    total_pnl: float = 0.0
    pending_orders: Dict[str, Dict] = field(default_factory=dict) # symbol -> order info with TP/SL params (bot-tracked)
    exchange_open_orders: List[Dict] = field(default_factory=list) # Actual open orders from exchange
    orphaned_orders: List[Dict] = field(default_factory=list) # Orders found on exchange but not in state
    reconciliation_log: List[Dict] = field(default_factory=list) # Log of reconciliation actions
    metrics: Metrics = field(default_factory=Metrics)

# Global instance
bot_state = BotState()

def update_balance(balance: float):
    bot_state.balance = balance
    bot_state.last_update = datetime.datetime.now().isoformat()

def update_full_balance(total: float, free: float, used: float):
    """Update complete balance information."""
    bot_state.total_balance = total
    bot_state.free_balance = free
    bot_state.balance = total  # Keep backward compatibility
    bot_state.last_update = datetime.datetime.now().isoformat()

def update_exchange_open_orders(orders: List[Dict]):
    """Update the list of open orders from the exchange.
    
    Transforms ccxt order format to a frontend-friendly format.
    """
    formatted_orders = []
    for order in orders:
        formatted_order = {
            'order_id': order.get('id', ''),
            'symbol': order.get('symbol', ''),
            'type': order.get('type', ''),
            'side': order.get('side', '').upper(),
            'price': float(order.get('price', 0) or 0),
            'amount': float(order.get('amount', 0) or 0),
            'filled': float(order.get('filled', 0) or 0),
            'remaining': float(order.get('remaining', 0) or 0),
            'status': order.get('status', ''),
            'timestamp': order.get('datetime', ''),
            'reduce_only': order.get('reduceOnly', False),
            'stop_price': float(order.get('stopPrice', 0) or 0) if order.get('stopPrice') else None
        }
        formatted_orders.append(formatted_order)
    
    bot_state.exchange_open_orders = formatted_orders
    bot_state.metrics.open_exchange_orders_count = len(formatted_orders)

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
    """Update position information for a symbol.
    
    When a position closes (goes from existing to not existing),
    this function also updates any open trade in the history with
    the exit information and calculates the final PnL.
    
    Note: This function handles both ccxt unified format and raw Binance format.
    ccxt unified format uses: 'contracts', 'entryPrice', 'markPrice', 'unrealizedPnl', 'side'
    Binance raw format uses: 'positionAmt', 'entryPrice', 'markPrice', 'unRealizedProfit'
    """
    had_position = symbol in bot_state.positions
    old_position = bot_state.positions.get(symbol) if had_position else None
    
    if position:
        # Handle both ccxt unified format and Binance raw format
        # ccxt uses 'contracts', Binance uses 'positionAmt'
        position_amount = position.get('contracts', position.get('positionAmt', 0))
        if position_amount is None:
            position_amount = 0
        position_amount = float(position_amount)
        
        if position_amount != 0:
            # Determine side - ccxt may provide 'side' directly
            if 'side' in position and position['side']:
                side = position['side'].upper()
                if side == 'LONG' or side == 'BUY':
                    side = 'LONG'
                elif side == 'SHORT' or side == 'SELL':
                    side = 'SHORT'
                else:
                    side = 'LONG' if position_amount > 0 else 'SHORT'
            else:
                side = 'LONG' if position_amount > 0 else 'SHORT'
            
            # Get entry price - ccxt uses 'entryPrice'
            entry_price = float(position.get('entryPrice', 0) or 0)
            
            # Get mark price - ccxt uses 'markPrice'  
            mark_price = float(position.get('markPrice', 0) or 0)
            
            # Get unrealized PnL - ccxt uses 'unrealizedPnl', Binance uses 'unRealizedProfit'
            unrealized_pnl = position.get('unrealizedPnl', position.get('unRealizedProfit', 0))
            if unrealized_pnl is None:
                unrealized_pnl = 0
            unrealized_pnl = float(unrealized_pnl)
            
            # Get leverage
            leverage = float(position.get('leverage', 1) or 1)
            
            bot_state.positions[symbol] = {
                'symbol': symbol,
                'side': side,
                'size': abs(position_amount),
                'entry_price': entry_price,
                'mark_price': mark_price,
                'unrealized_pnl': unrealized_pnl,
                'leverage': leverage,
                'take_profit': position.get('take_profit'),  # Add TP
                'stop_loss': position.get('stop_loss')  # Add SL
            }
        elif symbol in bot_state.positions:
            # Position was closed - update the trade history
            if old_position:
                _close_trade_in_history(symbol, old_position)
            del bot_state.positions[symbol]
    elif symbol in bot_state.positions:
        # Position was closed - update the trade history
        if old_position:
            _close_trade_in_history(symbol, old_position)
        del bot_state.positions[symbol]


def _close_trade_in_history(symbol: str, old_position: Dict):
    """Find and update the open trade for this symbol with exit information.
    
    Args:
        symbol: The trading symbol (e.g., 'BTC/USDT')
        old_position: The position data before it was closed
        
    Note:
        Since trades are inserted at position 0 (most recent first),
        iterating from start finds the most recent open trade for this symbol.
    """
    # Find the most recent open trade for this symbol
    for trade in bot_state.trade_history:
        if trade.get('symbol') == symbol and trade.get('status') == 'OPEN':
            # Calculate exit price - prefer mark_price, fallback to entry_price
            exit_price = old_position.get('mark_price', 0)
            if exit_price == 0:
                exit_price = old_position.get('entry_price', 0)
                if exit_price > 0:
                    print(f"Warning: Using entry_price as exit_price fallback for {symbol}")
            
            entry_price = trade.get('entry_price', old_position.get('entry_price', 0))
            size = trade.get('size', old_position.get('size', 0))
            side = trade.get('side', old_position.get('side', 'LONG'))
            
            # Calculate PnL - handle both BUY/SELL and LONG/SHORT notation
            is_long = side in ('LONG', 'BUY')
            if is_long:
                pnl = (exit_price - entry_price) * size
            else:  # SHORT or SELL
                pnl = (entry_price - exit_price) * size
            
            # Update the trade
            trade['exit_price'] = exit_price
            trade['pnl'] = round(pnl, 2)
            trade['status'] = 'CLOSED'
            trade['exit_time'] = datetime.datetime.now().isoformat()
            
            # Update total PnL
            bot_state.total_pnl += pnl
            
            print(f"Trade closed for {symbol}: PnL = {pnl:.2f} USDT")
            break

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
