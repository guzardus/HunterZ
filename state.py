from typing import List, Dict, Any
from dataclasses import dataclass, field
import datetime
import json
import os

# Configuration constants
MAX_BALANCE_HISTORY_POINTS = 5000  # About 17 days at 5-minute intervals (enough for 2+ weeks)
MAX_RECONCILIATION_LOG_ENTRIES = 50  # Maximum entries in reconciliation log

@dataclass
class Metrics:
    """Metrics for tracking order activities"""
    pending_orders_count: int = 0
    open_exchange_orders_count: int = 0
    placed_orders_count: int = 0
    cancelled_orders_count: int = 0
    filled_orders_count: int = 0
    # New metrics for reconciliation tracking
    reconciliation_runs_count: int = 0
    reconciliation_skipped_count: int = 0
    duplicate_placement_attempts: int = 0
    order_create_retries_total: int = 0
    pending_order_stale_count: int = 0

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
    balance_history: List[Dict] = field(default_factory=list) # Portfolio balance over time
    # Track previously logged pending order IDs to reduce log noise
    _logged_pending_order_ids: Dict[str, str] = field(default_factory=dict)  # symbol -> order_id
    # Track positions that have already warned about exit_price fallback
    _exit_price_fallback_warned: set = field(default_factory=set)  # set of symbols

# Global instance
bot_state = BotState()

def update_balance(balance: float):
    bot_state.balance = balance
    bot_state.last_update = datetime.datetime.now().isoformat()

def update_full_balance(total: float, free: float, used: float):
    """Update complete balance information and track history."""
    bot_state.total_balance = total
    bot_state.free_balance = free
    bot_state.balance = total  # Keep backward compatibility
    bot_state.last_update = datetime.datetime.now().isoformat()
    
    # Track balance history
    timestamp = datetime.datetime.now().isoformat()
    bot_state.balance_history.append({
        'timestamp': timestamp,
        'total_balance': total,
        'free_balance': free,
        'used_balance': used,
        'total_pnl': bot_state.total_pnl
    })
    
    # Trim to keep only MAX_BALANCE_HISTORY_POINTS most recent entries
    if len(bot_state.balance_history) > MAX_BALANCE_HISTORY_POINTS:
        bot_state.balance_history = bot_state.balance_history[-MAX_BALANCE_HISTORY_POINTS:]
    
    # Save balance history to disk
    save_balance_history()
    
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
        position_amount = float(position.get('contracts', position.get('positionAmt', 0)) or 0)
        
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
            
            # Note: TP/SL will be derived from open orders via compute_position_tp_sl()
            # We keep the position fields for backward compatibility
            
            # Preserve entry_time if position already exists, otherwise set current time
            existing_pos = bot_state.positions.get(symbol)
            if existing_pos and 'entry_time' in existing_pos:
                entry_time = existing_pos['entry_time']
            else:
                entry_time = datetime.datetime.now().isoformat()
            
            bot_state.positions[symbol] = {
                'symbol': symbol,
                'side': side,
                'size': abs(position_amount),
                'entry_price': entry_price,
                'mark_price': mark_price,
                'unrealized_pnl': unrealized_pnl,
                'leverage': leverage,
                'entry_time': entry_time,  # Track when position was opened
                'take_profit': position.get('take_profit'),  # Kept for backward compatibility
                'stop_loss': position.get('stop_loss')  # Kept for backward compatibility
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


def _normalize_order_field(order: Dict, field_name: str, fallback_name: str = None):
    """Helper to normalize order field names across different exchange formats.
    
    Some exchanges use camelCase (e.g., reduceOnly, stopPrice) while others
    use snake_case (e.g., reduce_only, stop_price).
    
    Args:
        order: Order dictionary
        field_name: Primary field name to check
        fallback_name: Alternative field name if primary not found
        
    Returns:
        Field value or None if not found
    """
    value = order.get(field_name)
    if value is None and fallback_name:
        value = order.get(fallback_name)
    return value


def compute_position_tp_sl(symbol: str, exchange_open_orders: List[Dict]) -> Dict:
    """Compute TP/SL for a position by deriving from exchange open orders.
    
    This function looks for STOP_MARKET and TAKE_PROFIT_MARKET orders
    that match the symbol and extracts their stop prices.
    
    Args:
        symbol: Trading symbol
        exchange_open_orders: List of open orders from the exchange
        
    Returns:
        dict: {'take_profit': float or None, 'stop_loss': float or None}
    """
    take_profit = None
    stop_loss = None
    
    for order in exchange_open_orders:
        if order.get('symbol') != symbol:
            continue
        
        order_type = order.get('type', '').upper()
        is_reduce_only = _normalize_order_field(order, 'reduceOnly', 'reduce_only')
        
        # Check if it's a TP/SL order
        if is_reduce_only or order_type in ['STOP_MARKET', 'TAKE_PROFIT_MARKET']:
            stop_price = _normalize_order_field(order, 'stopPrice', 'stop_price')
            if stop_price:
                stop_price = float(stop_price)
                
                if order_type == 'STOP_MARKET':
                    stop_loss = stop_price
                elif order_type == 'TAKE_PROFIT_MARKET':
                    take_profit = stop_price
    
    return {'take_profit': take_profit, 'stop_loss': stop_loss}


def enrich_positions_with_tp_sl():
    """Enrich all positions with TP/SL derived from exchange open orders.
    
    This should be called after updating exchange_open_orders to ensure
    position data includes current TP/SL information.
    """
    for symbol, position in bot_state.positions.items():
        tp_sl = compute_position_tp_sl(symbol, bot_state.exchange_open_orders)
        
        # Update position with derived TP/SL
        if tp_sl['take_profit'] is not None:
            position['take_profit'] = tp_sl['take_profit']
        if tp_sl['stop_loss'] is not None:
            position['stop_loss'] = tp_sl['stop_loss']


def _close_trade_in_history(symbol: str, old_position: Dict):
    """Find and update the open trade for this symbol with exit information.
    
    Args:
        symbol: The trading symbol (e.g., 'BTC/USDC')
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
                if exit_price > 0 and should_warn_exit_price_fallback(symbol):
                    print(f"Warning: Using entry_price as exit_price fallback for {symbol} (mark_price was 0 or unavailable)")
            
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
            
            # Save trade history after closing a trade
            save_trade_history()
            
            # Clear the exit price fallback warning tracking for this symbol
            clear_exit_price_fallback_warning(symbol)
            
            print(f"Trade closed for {symbol}: PnL = {pnl:.2f} USDC")
            break

def add_trade(trade: Dict):
    """Add a trade to history"""
    trade['timestamp'] = datetime.datetime.now().isoformat()
    bot_state.trade_history.insert(0, trade)
    save_trade_history()

def update_total_pnl(pnl: float):
    """Update total PnL"""
    bot_state.total_pnl = pnl

def add_pending_order(symbol: str, order_id: str, params: Dict):
    """Track a pending limit order with its intended TP/SL parameters.
    
    Stores created_at timestamp for stale order detection.
    """
    now = datetime.datetime.now().isoformat()
    bot_state.pending_orders[symbol] = {
        'order_id': order_id,
        'params': params,
        'timestamp': now,
        'created_at': now,  # For stale detection
        'exchange_orders': {'sl': None, 'tp': None},
        'last_tp_sl_placement': None
    }
    bot_state.metrics.pending_orders_count = len(bot_state.pending_orders)
    save_pending_orders()

def remove_pending_order(symbol: str):
    """Remove a pending order once processed"""
    if symbol in bot_state.pending_orders:
        del bot_state.pending_orders[symbol]
        bot_state.metrics.pending_orders_count = len(bot_state.pending_orders)
        # Clear log tracking so future orders can be logged
        clear_pending_order_log_tracking(symbol)
        save_pending_orders()

def get_pending_order(symbol: str):
    """Get pending order info for a symbol"""
    pending = bot_state.pending_orders.get(symbol)
    if pending is None:
        return None
    # Backfill new fields for existing persisted data
    if 'exchange_orders' not in pending:
        pending['exchange_orders'] = {'sl': None, 'tp': None}
    if 'last_tp_sl_placement' not in pending:
        pending['last_tp_sl_placement'] = None
    return pending

def update_pending_order_exchange_orders(symbol: str, sl_order: Dict = None, tp_order: Dict = None):
    """Store exchange TP/SL order ids on the pending order and persist to disk."""
    pending = bot_state.pending_orders.get(symbol)
    if not pending:
        return
    exchange_orders = pending.get('exchange_orders') or {'sl': None, 'tp': None}
    if sl_order:
        if isinstance(sl_order, dict):
            sl_id = sl_order.get('id') or sl_order.get('order_id') or sl_order.get('clientOrderId')
        else:
            sl_id = sl_order
        if sl_id:
            exchange_orders['sl'] = sl_id
    if tp_order:
        if isinstance(tp_order, dict):
            tp_id = tp_order.get('id') or tp_order.get('order_id') or tp_order.get('clientOrderId')
        else:
            tp_id = tp_order
        if tp_id:
            exchange_orders['tp'] = tp_id
    pending['exchange_orders'] = exchange_orders
    pending['last_tp_sl_placement'] = datetime.datetime.now().isoformat()
    bot_state.pending_orders[symbol] = pending
    save_pending_orders()

def get_stale_pending_orders(stale_threshold_seconds: int) -> Dict[str, Dict]:
    """Get all pending orders that are older than the threshold.
    
    Args:
        stale_threshold_seconds: Number of seconds after which an order is considered stale
        
    Returns:
        Dict mapping symbol to pending order info for stale orders
    """
    import config  # Import here to avoid circular imports
    
    stale_orders = {}
    now = datetime.datetime.now()
    
    for symbol, pending in bot_state.pending_orders.items():
        created_at_str = pending.get('created_at') or pending.get('timestamp')
        if not created_at_str:
            continue
        
        try:
            created_at = datetime.datetime.fromisoformat(created_at_str)
            age_seconds = (now - created_at).total_seconds()
            
            if age_seconds > stale_threshold_seconds:
                stale_orders[symbol] = pending
                stale_orders[symbol]['age_seconds'] = age_seconds
        except (ValueError, TypeError):
            # Skip if timestamp is invalid
            continue
    
    return stale_orders

def should_log_pending_order_still_active(symbol: str, order_id: str) -> bool:
    """Check if we should log 'pending order still active' message.
    
    To reduce log noise, we only log this message the first time we
    detect a pending order is still active. Subsequent checks for the
    same order_id will not be logged.
    
    Args:
        symbol: Trading symbol
        order_id: The order ID being checked
        
    Returns:
        bool: True if we should log, False if already logged for this order
    """
    previously_logged_id = bot_state._logged_pending_order_ids.get(symbol)
    if previously_logged_id == order_id:
        # Already logged for this order, don't log again
        return False
    # New order or different order, mark as logged and return True
    bot_state._logged_pending_order_ids[symbol] = order_id
    return True

def clear_pending_order_log_tracking(symbol: str):
    """Clear the log tracking for a pending order when it's removed.
    
    This should be called when a pending order is removed/processed
    so that if a new order is placed for the same symbol, it will be logged.
    
    Args:
        symbol: Trading symbol
    """
    if symbol in bot_state._logged_pending_order_ids:
        del bot_state._logged_pending_order_ids[symbol]

def should_warn_exit_price_fallback(symbol: str) -> bool:
    """Check if we should warn about using entry_price as exit_price fallback.
    
    To reduce log noise, we only warn once per position close attempt.
    
    Args:
        symbol: Trading symbol
        
    Returns:
        bool: True if we should warn, False if already warned
    """
    if symbol in bot_state._exit_price_fallback_warned:
        return False
    bot_state._exit_price_fallback_warned.add(symbol)
    return True

def clear_exit_price_fallback_warning(symbol: str):
    """Clear the exit price fallback warning tracking for a symbol.
    
    Should be called when a trade is successfully closed.
    
    Args:
        symbol: Trading symbol
    """
    bot_state._exit_price_fallback_warned.discard(symbol)

# Persistence functions
PENDING_ORDERS_FILE = os.path.join(os.path.dirname(__file__), 'data', 'pending_orders.json')
METRICS_FILE = os.path.join(os.path.dirname(__file__), 'data', 'metrics.json')
TRADE_HISTORY_FILE = os.path.join(os.path.dirname(__file__), 'data', 'trade_history.json')
BALANCE_HISTORY_FILE = os.path.join(os.path.dirname(__file__), 'data', 'balance_history.json')

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
                # Backfill defaults for older persisted structures
                for symbol, pending in loaded.items():
                    if 'exchange_orders' not in pending:
                        pending['exchange_orders'] = {'sl': None, 'tp': None}
                    if 'last_tp_sl_placement' not in pending:
                        pending['last_tp_sl_placement'] = None
                    loaded[symbol] = pending
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
    # Keep only last MAX_RECONCILIATION_LOG_ENTRIES entries
    bot_state.reconciliation_log = bot_state.reconciliation_log[:MAX_RECONCILIATION_LOG_ENTRIES]

def add_forced_closure_log(symbol: str, reason: str, details: Dict):
    """Log a forced position closure event"""
    log_entry = {
        'timestamp': datetime.datetime.now().isoformat(),
        'action': 'forced_closure',
        'symbol': symbol,
        'reason': reason,
        'details': details
    }
    bot_state.reconciliation_log.insert(0, log_entry)
    bot_state.reconciliation_log = bot_state.reconciliation_log[:MAX_RECONCILIATION_LOG_ENTRIES]

def save_metrics():
    """Save metrics to disk"""
    try:
        os.makedirs(os.path.dirname(METRICS_FILE), exist_ok=True)
        metrics_data = {
            'pending_orders_count': bot_state.metrics.pending_orders_count,
            'open_exchange_orders_count': bot_state.metrics.open_exchange_orders_count,
            'placed_orders_count': bot_state.metrics.placed_orders_count,
            'cancelled_orders_count': bot_state.metrics.cancelled_orders_count,
            'filled_orders_count': bot_state.metrics.filled_orders_count,
            'reconciliation_runs_count': bot_state.metrics.reconciliation_runs_count,
            'reconciliation_skipped_count': bot_state.metrics.reconciliation_skipped_count,
            'duplicate_placement_attempts': bot_state.metrics.duplicate_placement_attempts,
            'order_create_retries_total': bot_state.metrics.order_create_retries_total,
            'pending_order_stale_count': bot_state.metrics.pending_order_stale_count
        }
        with open(METRICS_FILE, 'w') as f:
            json.dump(metrics_data, f, indent=2)
    except Exception as e:
        print(f"WARNING: Failed to save metrics: {e}")

def load_metrics_on_startup():
    """Load metrics from disk"""
    try:
        if os.path.exists(METRICS_FILE):
            with open(METRICS_FILE, 'r') as f:
                loaded = json.load(f)
                bot_state.metrics.pending_orders_count = loaded.get('pending_orders_count', 0)
                bot_state.metrics.open_exchange_orders_count = loaded.get('open_exchange_orders_count', 0)
                bot_state.metrics.placed_orders_count = loaded.get('placed_orders_count', 0)
                bot_state.metrics.cancelled_orders_count = loaded.get('cancelled_orders_count', 0)
                bot_state.metrics.filled_orders_count = loaded.get('filled_orders_count', 0)
                bot_state.metrics.reconciliation_runs_count = loaded.get('reconciliation_runs_count', 0)
                bot_state.metrics.reconciliation_skipped_count = loaded.get('reconciliation_skipped_count', 0)
                bot_state.metrics.duplicate_placement_attempts = loaded.get('duplicate_placement_attempts', 0)
                bot_state.metrics.order_create_retries_total = loaded.get('order_create_retries_total', 0)
                bot_state.metrics.pending_order_stale_count = loaded.get('pending_order_stale_count', 0)
                print(f"Loaded metrics from disk: {loaded}")
        else:
            print("No metrics file found, starting fresh")
    except json.JSONDecodeError as e:
        print(f"WARNING: Corrupted metrics file, starting fresh: {e}")
    except Exception as e:
        print(f"WARNING: Failed to load metrics: {e}")

def save_trade_history():
    """Save trade history to disk"""
    try:
        os.makedirs(os.path.dirname(TRADE_HISTORY_FILE), exist_ok=True)
        with open(TRADE_HISTORY_FILE, 'w') as f:
            json.dump(bot_state.trade_history, f, indent=2)
    except Exception as e:
        print(f"WARNING: Failed to save trade history: {e}")

def load_trade_history_on_startup():
    """Load trade history from disk"""
    try:
        if os.path.exists(TRADE_HISTORY_FILE):
            with open(TRADE_HISTORY_FILE, 'r') as f:
                loaded = json.load(f)
                bot_state.trade_history = loaded
                # Recalculate total P&L from closed trades
                total = 0.0
                for trade in loaded:
                    if trade.get('status') == 'CLOSED' and trade.get('pnl') is not None:
                        try:
                            pnl_value = float(trade['pnl'])
                            total += pnl_value
                        except (ValueError, TypeError) as e:
                            print(f"WARNING: Invalid P&L value in trade {trade.get('symbol', 'unknown')}: {e}")
                            continue
                bot_state.total_pnl = total
                print(f"Loaded {len(loaded)} trades from disk, total P&L: {total:.2f}")
        else:
            print("No trade history file found, starting fresh")
    except json.JSONDecodeError as e:
        print(f"WARNING: Corrupted trade history file, starting fresh: {e}")
        bot_state.trade_history = []
    except Exception as e:
        print(f"WARNING: Failed to load trade history: {e}")
        bot_state.trade_history = []

def save_balance_history():
    """Save balance history to disk"""
    try:
        # Create directory only if it doesn't exist
        data_dir = os.path.dirname(BALANCE_HISTORY_FILE)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
        
        with open(BALANCE_HISTORY_FILE, 'w') as f:
            json.dump(bot_state.balance_history, f, indent=2)
    except Exception as e:
        print(f"WARNING: Failed to save balance history: {e}")

def load_balance_history_on_startup():
    """Load balance history from disk"""
    try:
        if os.path.exists(BALANCE_HISTORY_FILE):
            with open(BALANCE_HISTORY_FILE, 'r') as f:
                loaded = json.load(f)
                bot_state.balance_history = loaded
                print(f"Loaded {len(loaded)} balance history entries from disk")
        else:
            print("No balance history file found, starting fresh")
    except json.JSONDecodeError as e:
        print(f"WARNING: Corrupted balance history file, starting fresh: {e}")
        bot_state.balance_history = []
    except Exception as e:
        print(f"WARNING: Failed to load balance history: {e}")
        bot_state.balance_history = []

def init():
    """Initialize state on startup"""
    print("Initializing bot state...")
    load_pending_orders_on_startup()
    load_metrics_on_startup()
    load_trade_history_on_startup()
    load_balance_history_on_startup()
    print("Bot state initialized")
