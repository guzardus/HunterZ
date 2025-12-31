import math
import time
import datetime
from datetime import timezone
from decimal import Decimal, ROUND_HALF_UP
import logging
import config
import state

logger = logging.getLogger(__name__)

# Log throttling state: {(category, symbol): {"last_logged": datetime, "count": int}}
_log_throttle_state = {}
LOG_THROTTLE_INTERVAL_SECONDS = 60  # Minimum interval between repeated warnings


def normalize_symbol(symbol):
    """Normalize symbol to canonical format for consistent lookups and comparisons.
    
    Handles variations like:
    - "XRP/USDT" vs "XRP/USDT:USDT" (futures suffix)
    - Inconsistent casing
    
    Returns the base symbol without futures suffix (e.g., "XRP/USDT").
    """
    if not symbol:
        return symbol
    
    # Uppercase for consistency
    symbol = symbol.upper()
    
    # Strip futures suffix (e.g., ":USDT" from "XRP/USDT:USDT")
    if ':' in symbol:
        symbol = symbol.split(':')[0]
    
    return symbol


def prices_are_equal(price1, price2, tick_size, tolerance_pct=0.001):
    """Check if two prices are equal within a tolerance.
    
    Uses the larger of:
    - tick_size: minimum price increment
    - tolerance_pct * expected_price: percentage-based tolerance (default 0.1%)
    
    Args:
        price1: First price to compare
        price2: Second price to compare  
        tick_size: Minimum price increment for the symbol
        tolerance_pct: Percentage tolerance as decimal (default 0.001 = 0.1%)
        
    Returns:
        bool: True if prices are within tolerance, False otherwise
    """
    if price1 is None or price2 is None:
        return False
    
    try:
        p1 = float(price1)
        p2 = float(price2)
        tick = float(tick_size) if tick_size and tick_size > 0 else 1e-8
        
        # Use max of tick size or percentage tolerance
        ref_price = max(abs(p1), abs(p2))
        pct_tolerance = ref_price * tolerance_pct if ref_price > 0 else 0
        tolerance = max(tick, pct_tolerance)
        
        return abs(p1 - p2) <= tolerance
    except (TypeError, ValueError):
        return False


def should_log_throttled(category, symbol, interval_seconds=None):
    """Check if a throttled log message should be emitted.
    
    Returns True if we should log, False if throttled.
    Also increments the suppressed count for summary logging.
    
    Args:
        category: Log category (e.g., "tp_sl_inconsistent", "pending_order_active")
        symbol: Trading symbol
        interval_seconds: Override default throttle interval
        
    Returns:
        tuple: (should_log: bool, suppressed_count: int)
    """
    global _log_throttle_state
    
    interval = interval_seconds or LOG_THROTTLE_INTERVAL_SECONDS
    key = (category, normalize_symbol(symbol) if symbol else "")
    now = datetime.datetime.now(timezone.utc)
    
    entry = _log_throttle_state.get(key)
    if entry is None:
        # First occurrence - should log
        _log_throttle_state[key] = {"last_logged": now, "count": 0}
        return True, 0
    
    elapsed = (now - entry["last_logged"]).total_seconds()
    if elapsed >= interval:
        # Enough time passed - should log
        suppressed = entry["count"]
        _log_throttle_state[key] = {"last_logged": now, "count": 0}
        return True, suppressed
    else:
        # Throttled - don't log, increment counter
        entry["count"] += 1
        return False, 0


def log_tp_sl_inconsistent_throttled(symbol, side, entry_price, tp, sl):
    """Log TP/SL inconsistency warning with throttling.
    
    Limits repeated warnings to at most once per minute per symbol.
    """
    should_log, suppressed = should_log_throttled("tp_sl_inconsistent", symbol)
    
    if should_log:
        msg = f"⚠️ Skipping closure for {symbol}: TP/SL inconsistent for {side} (entry {entry_price}, TP {tp}, SL {sl})"
        if suppressed > 0:
            msg += f" [repeated {suppressed} times in last {LOG_THROTTLE_INTERVAL_SECONDS}s]"
        logger.warning(msg)


def log_pending_order_active_throttled(order_id, symbol):
    """Log pending order still active message with throttling.
    
    Limits repeated messages to at most once per minute per symbol.
    """
    should_log, suppressed = should_log_throttled("pending_order_active", symbol)
    
    if should_log:
        msg = f"Pending order {order_id} still active for {symbol}, skipping new placement"
        if suppressed > 0:
            msg += f" [repeated {suppressed} times in last {LOG_THROTTLE_INTERVAL_SECONDS}s]"
        logger.info(msg)


def fetch_mark_price(client, symbol):
    """Fetch a best-effort current/mark price for the symbol."""
    try:
        resolved = client._resolve_symbol(symbol) if hasattr(client, "_resolve_symbol") else symbol
        ticker = client.exchange.fetch_ticker(resolved)
        # Prefer mark/last price fields when available
        for key in ("markPrice", "mark_price", "last", "close", "info"):
            if key == "info":
                info_price = ticker.get("info", {}).get("markPrice")
                if info_price:
                    return float(info_price)
                continue
            val = ticker.get(key)
            if val:
                return float(val)
    except Exception as exc:
        print(f"Warning: failed to fetch mark price for {symbol}: {exc}")
    return None


def fetch_symbol_tick_size(client, symbol):
    """Return price tick size for symbol; fallback to small default."""
    default_tick = 1e-8
    try:
        markets = client.exchange.markets or client.exchange.load_markets()
        resolved = client._resolve_symbol(symbol) if hasattr(client, "_resolve_symbol") else symbol
        market = markets.get(resolved) or markets.get(symbol)
        if not market:
            print(f"Warning: market metadata missing for {symbol}, using default tick")
            return default_tick
        # Try Binance filters first
        filters = market.get("info", {}).get("filters", [])
        for f in filters:
            if f.get("filterType") == "PRICE_FILTER" and f.get("tickSize"):
                return float(f["tickSize"])
        # Fallback to precision if present
        precision = market.get("precision", {}).get("price")
        if precision is not None:
            return float(math.pow(10, -precision))
    except Exception as exc:
        print(f"Warning: failed to fetch tick size for {symbol}: {exc}")
    return default_tick


def round_to_tick(value, tick_size):
    """Round a price to nearest valid tick."""
    if tick_size <= 0:
        return value
    tick = Decimal(str(tick_size))
    quantized = (Decimal(str(value)) / tick).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * tick
    return float(quantized)


def set_backoff(symbol, seconds=None):
    seconds = seconds or config.TP_SL_PENDING_BACKOFF_SECONDS
    expires = datetime.datetime.now(timezone.utc) + datetime.timedelta(seconds=seconds)
    state.bot_state.tp_sl_backoff[symbol] = {"until": expires.isoformat(), "logged": False}


def check_backoff(symbol):
    entry = state.bot_state.tp_sl_backoff.get(symbol)
    if not entry:
        return False, 0
    try:
        expires = datetime.datetime.fromisoformat(entry["until"])
    except Exception:
        del state.bot_state.tp_sl_backoff[symbol]
        return False, 0
    remaining = (expires - datetime.datetime.now(timezone.utc)).total_seconds()
    if remaining > 0:
        return True, remaining
    del state.bot_state.tp_sl_backoff[symbol]
    return False, 0


def place_market_reduce_only(client, symbol, amount, side, reason="fallback"):
    try:
        return client.close_position_market(symbol, side, amount, reason=reason)
    except Exception as exc:
        print(f"Fallback market close failed for {symbol}: {exc}")
        return None


def order_matches_target(order, target_price, target_amount, tick_size, amount_tolerance=0.01):
    """Check if an order matches the target price and amount.
    
    Args:
        order: Order dictionary from exchange
        target_price: Expected price for the order
        target_amount: Expected amount for the order
        tick_size: Minimum price increment for the symbol
        amount_tolerance: Tolerance for amount matching (default 1%)
        
    Returns:
        bool: True if order matches target within tolerances
    """
    if not order:
        return False
    
    # Get order price - check both stopPrice and price fields
    order_price = order.get('stopPrice') or order.get('stop_price') or order.get('price')
    if not order_price:
        return False
    
    try:
        order_price = float(order_price)
        order_amount = float(order.get('amount', 0))
        
        # Check if price matches within tick tolerance
        price_matches = prices_are_equal(order_price, target_price, tick_size)
        
        # Check if amount matches within tolerance
        amount_matches = abs(order_amount - target_amount) <= target_amount * amount_tolerance
        
        return price_matches and amount_matches
    except (TypeError, ValueError):
        return False


def safe_place_tp_sl(client, symbol, is_long, amount, computed_tp, computed_sl, *, cfg=config):
    """Place TP/SL with price pre-checks, rounding, buffer and fallback."""
    in_backoff, remaining = check_backoff(symbol)
    if in_backoff:
        entry = state.bot_state.tp_sl_backoff.get(symbol, {})
        if not entry.get("logged"):
            print(f"Skipping TP/SL for {symbol} due to backoff ({int(remaining)}s remaining)")
            entry["logged"] = True
            state.bot_state.tp_sl_backoff[symbol] = entry
        return False

    current_price = fetch_mark_price(client, symbol)
    tick_size = fetch_symbol_tick_size(client, symbol)
    buffer = tick_size * cfg.TP_SL_BUFFER_TICKS
    fallback_mode = cfg.TP_SL_FALLBACK_MODE.upper()
    if fallback_mode not in ("MARKET_REDUCE", "NONE"):
        print(f"Invalid TP_SL_FALLBACK_MODE={fallback_mode}, defaulting to MARKET_REDUCE")
        fallback_mode = "MARKET_REDUCE"

    rounded_tp = round_to_tick(computed_tp, tick_size)
    rounded_sl = round_to_tick(computed_sl, tick_size)

    close_side = "sell" if is_long else "buy"

    print(f"[TP/SL] {symbol} side={'LONG' if is_long else 'SHORT'} "
          f"amt={amount} current={current_price} tick={tick_size} "
          f"raw_tp={computed_tp} raw_sl={computed_sl} "
          f"tp={rounded_tp} sl={rounded_sl} buffer={buffer}")

    if current_price is None:
        print(f"Cannot place TP/SL for {symbol}: missing current price")
        set_backoff(symbol)
        return False

    tp_crossed = False
    sl_crossed = False
    if is_long:
        tp_crossed = rounded_tp <= current_price + buffer
        sl_crossed = rounded_sl >= current_price - buffer
    else:
        tp_crossed = rounded_tp >= current_price - buffer
        sl_crossed = rounded_sl <= current_price + buffer

    result = False
    try:
        if tp_crossed or sl_crossed:
            reason = "tp_already_crossed" if tp_crossed else "sl_already_crossed"
            if fallback_mode == "MARKET_REDUCE":
                print(f"{symbol} {reason}: placing market reduce-only close")
                order = place_market_reduce_only(client, symbol, amount, close_side, reason=reason)
                result = order is not None
            else:
                print(f"{symbol} {reason} but fallback mode {fallback_mode} prevents market close")
        else:
            sl_res = client.place_stop_loss(symbol, close_side, amount, rounded_sl)
            if not sl_res:
                print(f"Failed placing SL for {symbol}, skipping TP placement")
                result = False
            else:
                tp_res = client.place_take_profit(symbol, close_side, amount, rounded_tp)
                result = bool(tp_res)
                if not result:
                    print(f"Failed placing TP for {symbol} after SL success")
    except Exception as exc:
        print(f"Error placing TP/SL for {symbol}: {exc}")
        result = False
    finally:
        set_backoff(symbol)
    return result
