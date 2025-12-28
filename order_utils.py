import math
import time
import datetime
from datetime import timezone
from decimal import Decimal, ROUND_HALF_UP
import config
import state


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
