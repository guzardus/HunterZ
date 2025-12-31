import ccxt
import config
import logging
import time

logger = logging.getLogger(__name__)

# Retry configuration for order placement
MAX_ORDER_RETRIES = 3
RETRY_BACKOFF_SECONDS = [0.5, 1.0, 2.0]

# Tolerances for order matching
PRICE_TOLERANCE_PCT = 0.001  # 0.1% tolerance for price matching
QUANTITY_TOLERANCE_PCT = 0.01  # 1% tolerance for quantity matching


def approx_equal(a, b, pct_tol=0.01):
    """
    Check if two values are approximately equal within a percentage tolerance.
    
    Args:
        a: First value
        b: Second value  
        pct_tol: Percentage tolerance (default 1%)
        
    Returns:
        bool: True if values are approximately equal
    """
    if a == 0 and b == 0:
        return True
    if a == 0 or b == 0:
        return False
    return abs(a - b) / max(abs(a), abs(b)) <= pct_tol


def order_matches_target(order, target_price, target_qty, price_tol=PRICE_TOLERANCE_PCT, qty_tol=QUANTITY_TOLERANCE_PCT):
    """
    Check if an existing order matches the target price and quantity.
    
    Args:
        order: Order dict from exchange
        target_price: Expected price/stop price
        target_qty: Expected quantity
        price_tol: Tolerance for price matching
        qty_tol: Tolerance for quantity matching
        
    Returns:
        bool: True if order matches target within tolerances
    """
    if not order:
        return False
    
    # Get order price - check both regular price and stop price
    order_price = float(order.get('stopPrice', 0) or order.get('price', 0) or 0)
    order_qty = float(order.get('amount', 0) or order.get('remaining', 0) or 0)
    
    if order_price == 0 or order_qty == 0:
        return False
    
    price_matches = approx_equal(order_price, float(target_price), price_tol)
    qty_matches = approx_equal(order_qty, float(target_qty), qty_tol)
    
    logger.debug("order_matches_target: order_price=%s target_price=%s price_matches=%s, order_qty=%s target_qty=%s qty_matches=%s",
                 order_price, target_price, price_matches, order_qty, target_qty, qty_matches)
    
    return price_matches and qty_matches


def _find_matching_reduce_only_from_state(symbol, target_price, target_qty, orders=None):
    """
    Check the cached exchange_open_orders in state for a matching reduce-only order.
    This helps avoid duplicate placements when the exchange API response lags.
    """
    import state  # Local import to avoid circular dependency

    cached_orders = orders or state.bot_state.exchange_open_orders

    for order in cached_orders:
        mapped_order = {
            'id': order.get('order_id') or order.get('id'),
            'stopPrice': order.get('stop_price') or order.get('price'),
            'price': order.get('price'),
            'amount': order.get('amount')
        }
        if order_matches_target(mapped_order, target_price, target_qty):
            return mapped_order
    return None


def _validate_order_response(resp):
    """
    Ensure the order response contains at least one valid ID field.
    Returns the response dict if valid, None if invalid or missing ID.
    
    Args:
        resp: Order response from exchange
        
    Returns:
        dict: The full response if valid, None if invalid/missing ID
        
    Note:
        An order ID is considered valid if it is truthy (non-None, non-empty, non-zero).
        This handles the common case where exchanges return None or empty string for failed orders.
    """
    if not resp:
        return None
    # common ID fields used across exchanges
    order_id = None
    if isinstance(resp, dict):
        order_id = resp.get('id') or resp.get('orderId') or resp.get('client_order_id') or resp.get('clientOrderId')
    if not order_id:
        return None
    return resp


def _is_transient_error(error):
    """
    Check if an error is transient and worth retrying.
    
    Args:
        error: The exception to check
        
    Returns:
        bool: True if the error is transient, False otherwise
    """
    transient_indicators = [
        'timeout', 'network', 'connection', 'temporary',
        'rate limit', 'too many requests', '429', '503', '504'
    ]
    error_str = str(error).lower()
    return any(indicator in error_str for indicator in transient_indicators)


class HyperliquidClient:
    def __init__(self):
        # Requires ccxt >= 4.4.0 for Hyperliquid support
        self.exchange = ccxt.hyperliquid({
            'walletAddress': config.WALLET_ADDRESS,
            'privateKey': config.PRIVATE_KEY,
            'options': {
                'defaultType': 'swap'
            }
        })
        print("Hyperliquid Live Trading Enabled")

    def fetch_ohlcv(self, symbol, timeframe=config.TIMEFRAME, limit=100):
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            return ohlcv
        except Exception as e:
            print(f"Error fetching OHLCV for {symbol}: {e}")
            return []

    def get_balance(self):
        try:
            balance = self.exchange.fetch_balance()
            usdc_balance = balance.get('USDC', {})
            free_value = usdc_balance.get('free', 0)
            return float(free_value)
        except Exception as e:
            print(f"Error fetching balance: {e}")
            return 0.0

    def get_full_balance(self):
        """Get complete balance information including total, free, and used."""
        try:
            balance = self.exchange.fetch_balance()
            usdc_balance = balance.get('USDC', {})
            return {
                'total': float(usdc_balance.get('total', 0)),
                'free': float(usdc_balance.get('free', 0)),
                'used': float(usdc_balance.get('used', 0))
            }
        except Exception as e:
            print(f"Error fetching full balance: {e}")
            return {'total': 0.0, 'free': 0.0, 'used': 0.0}

    def get_position(self, symbol):
        try:
            positions = self.exchange.fetch_positions([symbol])
            for pos in positions:
                if pos['symbol'] == symbol:
                    return pos
            return None
        except Exception as e:
            print(f"Error fetching position for {symbol}: {e}")
            return None

    def get_all_positions(self):
        """Fetch all open positions from the exchange."""
        try:
            positions = self.exchange.fetch_positions()
            # Filter to only positions with non-zero amounts
            open_positions = []
            for pos in positions:
                contracts = float(pos.get('contracts', 0) or 0)
                if contracts != 0:
                    open_positions.append(pos)
            return open_positions
        except Exception as e:
            print(f"Error fetching all positions: {e}")
            return []

    def get_all_open_orders(self):
        """Fetch all open orders from the exchange across all trading pairs."""
        try:
            all_orders = []
            for symbol in config.TRADING_PAIRS:
                try:
                    symbol_orders = self.exchange.fetch_open_orders(symbol)
                    all_orders.extend(symbol_orders)
                except Exception as symbol_err:
                    print(f"Error fetching open orders for {symbol}: {symbol_err}")
            return all_orders
        except Exception as e:
            print(f"Error fetching all open orders: {e}")
            return []

    def get_recent_trades(self, symbol=None, limit=50):
        """Fetch recent closed trades/fills from the exchange."""
        try:
            if symbol:
                trades = self.exchange.fetch_my_trades(symbol, limit=limit)
            else:
                # Fetch trades for all trading pairs
                all_trades = []
                for pair in config.TRADING_PAIRS:
                    try:
                        trades = self.exchange.fetch_my_trades(pair, limit=10)
                        all_trades.extend(trades)
                    except Exception as e:
                        print(f"Error fetching trades for {pair}: {e}")
                # Sort by timestamp descending
                all_trades.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
                return all_trades[:limit]
            return trades
        except Exception as e:
            print(f"Error fetching recent trades: {e}")
            return []

    def cancel_all_orders(self, symbol):
        try:
            orders = self.exchange.fetch_open_orders(symbol)
            if not orders:
                print(f"No open orders to cancel for {symbol}")
                return True
            success_count = 0
            failed = 0
            skipped = 0
            for order in orders:
                order_id = order.get('id')
                if not order_id:
                    skipped += 1
                    print(f"Order missing id for {symbol}, skipping cancel")
                    continue
                try:
                    self.exchange.cancel_order(order_id, symbol)
                    success_count += 1
                    print(f"Cancelled order {order_id} for {symbol}")
                except Exception as order_error:
                    failed += 1
                    print(f"Error cancelling order {order_id} for {symbol}: {order_error}")
            cancelled = success_count
            success = failed == 0
            print(f"Manually cancelled {cancelled} orders for {symbol} (failed: {failed}, skipped: {skipped}, success: {success})")
            return success
        except Exception as e:
            print(f"Error in manual cancel_all_orders for {symbol}: {e}")
            return False

    def place_limit_order(self, symbol, side, amount, price):
        """Place a limit order with validation, logging, and retries.
        
        Args:
            symbol: Trading symbol
            side: 'buy' or 'sell'
            amount: Order quantity
            price: Limit price
            
        Returns:
            dict: Order response if successful, None otherwise
        """
        payload = {
            'symbol': symbol,
            'type': 'limit',
            'side': side,
            'amount': amount,
            'price': price
        }
        
        for attempt in range(MAX_ORDER_RETRIES):
            try:
                order = self.exchange.create_order(symbol, 'limit', side, amount, price)
                logger.debug("create_order payload=%s response=%s", payload, order)
                
                validated = _validate_order_response(order)
                if validated:
                    print(f"Placed {side} limit order for {symbol} at {price}")
                    return validated
                else:
                    logger.error("Limit order response invalid/missing id. Response: %s", order)
                    # Retry on None response
                    if attempt < MAX_ORDER_RETRIES - 1:
                        time.sleep(RETRY_BACKOFF_SECONDS[attempt])
                        continue
                    return None
                    
            except Exception as e:
                logger.debug("create_order attempt %d failed: payload=%s error=%s", attempt + 1, payload, e)
                if _is_transient_error(e) and attempt < MAX_ORDER_RETRIES - 1:
                    time.sleep(RETRY_BACKOFF_SECONDS[attempt])
                    continue
                print(f"Error placing limit order for {symbol}: {e}")
                return None
        
        return None

    def place_stop_loss(self, symbol, side, amount, stop_price):
        """Place a stop loss order with validation, logging, and retries.
        
        Args:
            symbol: Trading symbol
            side: 'buy' or 'sell' (close side)
            amount: Order quantity
            stop_price: Stop trigger price
            
        Returns:
            dict: Order response if successful, None otherwise
        """
        # Note: For Hyperliquid via CCXT, STOP_MARKET orders require a price parameter
        # even though they execute at market. We use stop_price as the price.
        # Also use 'stopLossPrice' as the preferred param key for the trigger.
        params = {'stopLossPrice': stop_price, 'reduceOnly': True}
        payload = {
            'symbol': symbol,
            'type': 'STOP_MARKET',
            'side': side,
            'amount': amount,
            'price': stop_price,
            'params': params
        }
        
        for attempt in range(MAX_ORDER_RETRIES):
            try:
                order = self.exchange.create_order(symbol, 'STOP_MARKET', side, amount, stop_price, params=params)
                logger.debug("create_order payload=%s response=%s", payload, order)
                
                validated = _validate_order_response(order)
                if validated:
                    print(f"Placed Stop Loss for {symbol} at {stop_price}")
                    return validated
                else:
                    logger.error("SL order response invalid/missing id. Response: %s", order)
                    if attempt < MAX_ORDER_RETRIES - 1:
                        time.sleep(RETRY_BACKOFF_SECONDS[attempt])
                        continue
                    return None
                    
            except Exception as e:
                logger.debug("create_order SL attempt %d failed: payload=%s error=%s", attempt + 1, payload, e)
                if _is_transient_error(e) and attempt < MAX_ORDER_RETRIES - 1:
                    time.sleep(RETRY_BACKOFF_SECONDS[attempt])
                    continue
                print(f"Error placing SL for {symbol}: {e}")
                return None
        
        return None

    def place_take_profit(self, symbol, side, amount, tp_price):
        """Place a take profit order with validation, logging, and retries.
        
        Args:
            symbol: Trading symbol
            side: 'buy' or 'sell' (close side)
            amount: Order quantity
            tp_price: Take profit trigger price
            
        Returns:
            dict: Order response if successful, None otherwise
        """
        # Note: For Hyperliquid via CCXT, TAKE_PROFIT_MARKET orders require a price parameter
        # even though they execute at market. We use tp_price as the price.
        # Also use 'takeProfitPrice' as the preferred param key for the trigger.
        params = {'takeProfitPrice': tp_price, 'reduceOnly': True}
        payload = {
            'symbol': symbol,
            'type': 'TAKE_PROFIT_MARKET',
            'side': side,
            'amount': amount,
            'price': tp_price,
            'params': params
        }
        
        for attempt in range(MAX_ORDER_RETRIES):
            try:
                order = self.exchange.create_order(symbol, 'TAKE_PROFIT_MARKET', side, amount, tp_price, params=params)
                logger.debug("create_order payload=%s response=%s", payload, order)
                
                validated = _validate_order_response(order)
                if validated:
                    print(f"Placed Take Profit for {symbol} at {tp_price}")
                    return validated
                else:
                    logger.error("TP order response invalid/missing id. Response: %s", order)
                    if attempt < MAX_ORDER_RETRIES - 1:
                        time.sleep(RETRY_BACKOFF_SECONDS[attempt])
                        continue
                    return None
                    
            except Exception as e:
                logger.debug("create_order TP attempt %d failed: payload=%s error=%s", attempt + 1, payload, e)
                if _is_transient_error(e) and attempt < MAX_ORDER_RETRIES - 1:
                    time.sleep(RETRY_BACKOFF_SECONDS[attempt])
                    continue
                print(f"Error placing TP for {symbol}: {e}")
                return None
        
        return None

    def get_order_status(self, symbol, order_id):
        """Check the status of an order."""
        try:
            order = self.exchange.fetch_order(order_id, symbol)
            return order
        except Exception as e:
            print(f"Error fetching order status for {symbol}: {e}")
            return None

    def place_sl_tp_orders(self, symbol, side, amount, sl_price, tp_price):
        """Place both Stop Loss and Take Profit orders together.
        
        This function is idempotent - it checks for existing matching orders
        before placing new ones to prevent duplicates.
        
        Args:
            symbol: Trading symbol
            side: 'buy' or 'sell' (entry side, TP/SL will use opposite)
            amount: Order quantity
            sl_price: Stop loss price
            tp_price: Take profit price
            
        Returns:
            dict: {'sl_order': order or None, 'tp_order': order or None}
        """
        import state  # Import here to avoid circular imports
        
        sl_tp_side = 'sell' if side == 'buy' else 'buy'

        def _select_matching_order(candidates, target_price, target_qty):
            if not candidates:
                return None
            for candidate in candidates:
                if order_matches_target(candidate, target_price, target_qty, qty_tol=config.TP_SL_QUANTITY_TOLERANCE):
                    return candidate
            return candidates[0]
        
        # Check for existing matching orders first
        existing_tp_sl = self.get_tp_sl_orders_for_position(symbol)
        existing_sl = _select_matching_order(existing_tp_sl.get('sl_orders', []), sl_price, amount)
        existing_tp = _select_matching_order(existing_tp_sl.get('tp_orders', []), tp_price, amount)

        # Use cached exchange_open_orders as a secondary source to avoid duplicates when API lags
        state_reduce_orders = None
        if not existing_sl or not existing_tp:
            state_reduce_orders = [
                o for o in state.bot_state.exchange_open_orders
                if o.get('symbol') == symbol and o.get('reduce_only')
            ]
        if not existing_sl:
            state_match_sl = _find_matching_reduce_only_from_state(symbol, sl_price, amount, state_reduce_orders)
            if state_match_sl:
                existing_sl = state_match_sl
        if not existing_tp:
            state_match_tp = _find_matching_reduce_only_from_state(symbol, tp_price, amount, state_reduce_orders)
            if state_match_tp:
                existing_tp = state_match_tp
        
        sl_order = None
        tp_order = None
        
        # Check if SL already exists and matches
        if existing_sl and order_matches_target(existing_sl, sl_price, amount):
            logger.info("Existing SL order matches target for %s, skipping placement", symbol)
            sl_order = existing_sl
            state.bot_state.metrics.duplicate_placement_attempts += 1
        else:
            # Cancel existing mismatched SL if present
            if existing_sl:
                old_sl_id = existing_sl.get('id')
                logger.info("Existing SL order for %s does not match target, cancelling %s", symbol, old_sl_id)
                self.cancel_order(symbol, old_sl_id)
            sl_order = self.place_stop_loss(symbol, sl_tp_side, amount, sl_price)
            # Update state immediately after successful order placement
            if sl_order:
                self._update_state_after_order(symbol, sl_order)
        
        # Check if TP already exists and matches
        if existing_tp and order_matches_target(existing_tp, tp_price, amount):
            logger.info("Existing TP order matches target for %s, skipping placement", symbol)
            tp_order = existing_tp
            state.bot_state.metrics.duplicate_placement_attempts += 1
        else:
            # Cancel existing mismatched TP if present
            if existing_tp:
                old_tp_id = existing_tp.get('id')
                logger.info("Existing TP order for %s does not match target, cancelling %s", symbol, old_tp_id)
                self.cancel_order(symbol, old_tp_id)
            tp_order = self.place_take_profit(symbol, sl_tp_side, amount, tp_price)
            # Update state immediately after successful order placement
            if tp_order:
                self._update_state_after_order(symbol, tp_order)
        
        return {'sl_order': sl_order, 'tp_order': tp_order}
    
    def _update_state_after_order(self, symbol, order):
        """Update bot state immediately after a successful order placement.
        
        This prevents race conditions where subsequent reconciliation thinks
        the order is missing and re-creates it.
        
        Args:
            symbol: Trading symbol
            order: Order response dict
        """
        import state  # Import here to avoid circular imports
        
        try:
            # Refresh open orders for this symbol to ensure state is current
            orders = self.get_open_orders(symbol)
            
            # Update exchange_open_orders in state
            # Filter out orders for this symbol and add fresh ones
            other_orders = [o for o in state.bot_state.exchange_open_orders 
                          if o.get('symbol') != symbol]
            
            # Format new orders to match expected state format
            formatted_orders = []
            for o in orders:
                formatted_order = {
                    'order_id': o.get('id', ''),
                    'symbol': o.get('symbol', ''),
                    'type': o.get('type', ''),
                    'side': o.get('side', '').upper(),
                    'price': float(o.get('price', 0) or 0),
                    'amount': float(o.get('amount', 0) or 0),
                    'filled': float(o.get('filled', 0) or 0),
                    'remaining': float(o.get('remaining', 0) or 0),
                    'status': o.get('status', ''),
                    'timestamp': o.get('datetime', ''),
                    'reduce_only': o.get('reduceOnly', False),
                    'stop_price': float(o.get('stopPrice', 0) or 0) if o.get('stopPrice') else None
                }
                formatted_orders.append(formatted_order)
            
            state.bot_state.exchange_open_orders = other_orders + formatted_orders
            state.bot_state.metrics.open_exchange_orders_count = len(state.bot_state.exchange_open_orders)
            
            logger.debug("Updated state after order placement for %s", symbol)
        except Exception as e:
            logger.warning("Failed to update state after order placement for %s: %s", symbol, e)

    def get_open_orders(self, symbol=None):
        """Fetch open orders from the exchange.
        
        Args:
            symbol: Optional symbol to filter orders. If None, fetches all open orders.
            
        Returns:
            list: List of open orders
        """
        try:
            if symbol:
                orders = self.exchange.fetch_open_orders(symbol)
            else:
                orders = self.exchange.fetch_open_orders()
            return orders
        except Exception as e:
            print(f"Error fetching open orders for {symbol if symbol else 'all symbols'}: {e}")
            return []
    
    def get_tp_sl_orders_for_position(self, symbol):
        """Get TP/SL orders for a specific symbol.
        
        Uses normalized symbol comparison to handle format differences between
        exchange order symbols (e.g., "BTC/USDC") and position symbols 
        (e.g., "BTC/USDC:USDC").
        
        Args:
            symbol: Trading symbol to check for TP/SL orders
            
        Returns:
            dict: {'sl_orders': [orders], 'tp_orders': [orders]}
        """
        from utils import normalize_symbol, TP_SL_ORDER_TYPES
        
        try:
            orders = self.get_open_orders(symbol)
            sl_orders = []
            tp_orders = []
            
            # Use normalized symbol for comparison
            norm_target = normalize_symbol(symbol)
            
            # Debug logging to help diagnose order matching issues
            if orders:
                logger.debug("get_tp_sl_orders_for_position: Checking %d open orders for %s (normalized: %s). "
                           "Types found: %s", len(orders), symbol, norm_target,
                           [o.get('type') for o in orders])
            
            for order in orders:
                # Normalize the order's symbol before comparing
                order_symbol = order.get('symbol')
                if not order_symbol or normalize_symbol(order_symbol) != norm_target:
                    continue
                
                order_type = str(order.get('type', '')).upper()
                is_reduce_only = order.get('reduceOnly', order.get('reduce_only', False))
                
                # Check for stopPrice presence - Hyperliquid/Binance-flavor TP/SL detection
                # Some exchanges use stopPrice even with generic order types
                stop_price_val = order.get('stopPrice', order.get('stop_price'))
                has_stop_price = False
                if stop_price_val is not None:
                    try:
                        has_stop_price = float(stop_price_val) > 0
                    except (ValueError, TypeError):
                        # If stopPrice is not a valid number, treat as not having stop price
                        pass
                
                # Identify TP/SL orders using multiple indicators:
                # 1. reduceOnly flag
                # 2. Specific order types (STOP_MARKET, TAKE_PROFIT_MARKET, etc.)
                # 3. Presence of stopPrice
                is_tp_sl_candidate = is_reduce_only or has_stop_price or order_type in TP_SL_ORDER_TYPES
                if is_tp_sl_candidate:
                    # Determine if this is SL or TP based on order type
                    if 'STOP' in order_type and 'TAKE_PROFIT' not in order_type:
                        sl_orders.append(order)
                    elif 'TAKE_PROFIT' in order_type:
                        tp_orders.append(order)
                    elif has_stop_price:
                        # Fallback: if it has stopPrice but type is ambiguous,
                        # log for debugging and treat as SL for reconciliation coverage
                        logger.debug("get_tp_sl_orders_for_position: Ambiguous reduce-only/stopPrice order "
                                     "type '%s' for %s", order_type, symbol)
                        sl_orders.append(order)
            
            # Debug: log if no matches found despite having orders
            if orders and not sl_orders and not tp_orders:
                logger.debug("get_tp_sl_orders_for_position: Checking %d open orders for %s. "
                           "Types found: %s. reduceOnly flags: %s. stopPrices: %s",
                           len(orders), symbol,
                           [o.get('type') for o in orders],
                           [o.get('reduceOnly') for o in orders],
                           [o.get('stopPrice') for o in orders])
            
            return {'sl_orders': sl_orders, 'tp_orders': tp_orders}
        except Exception as e:
            print(f"Error getting TP/SL orders for {symbol}: {e}")
            return {'sl_orders': [], 'tp_orders': []}
    
    def cancel_order(self, symbol, order_id):
        """Cancel a specific order.
        
        Args:
            symbol: Trading symbol
            order_id: Order ID to cancel
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.exchange.cancel_order(order_id, symbol)
            print(f"Cancelled order {order_id} for {symbol}")
            return True
        except Exception as e:
            print(f"Error cancelling order {order_id} for {symbol}: {e}")
            return False
    
    def close_position_market(self, symbol, side, amount, reason="manual"):
        """Close a position immediately with a market order.
        
        Args:
            symbol: Trading symbol
            side: 'buy' or 'sell' (opposite of position direction)
            amount: Position size to close
            reason: Reason for closure ("tp_breach", "sl_breach", "manual")
        
        Returns:
            order: Market order result or None
        """
        params = {'reduceOnly': True}
        payload = {
            'symbol': symbol,
            'type': 'market',
            'side': side,
            'amount': amount,
            'params': params,
            'reason': reason
        }
        
        for attempt in range(MAX_ORDER_RETRIES):
            try:
                order = self.exchange.create_order(symbol, 'market', side, amount, params=params)
                logger.debug("create_order payload=%s response=%s", payload, order)
                
                validated = _validate_order_response(order)
                if validated:
                    print(f"⚠️ FORCED CLOSURE ({reason}): Closed {amount} {symbol} position with market {side} order")
                    return validated
                else:
                    logger.error("Market order response invalid/missing id. Response: %s", order)
                    if attempt < MAX_ORDER_RETRIES - 1:
                        time.sleep(RETRY_BACKOFF_SECONDS[attempt])
                        continue
                    return None
                    
            except Exception as e:
                logger.debug("create_order market attempt %d failed: payload=%s error=%s", attempt + 1, payload, e)
                if _is_transient_error(e) and attempt < MAX_ORDER_RETRIES - 1:
                    time.sleep(RETRY_BACKOFF_SECONDS[attempt])
                    continue
                print(f"Error closing position for {symbol} with market order: {e}")
                return None
        
        return None
