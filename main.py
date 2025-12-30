import time
import pandas as pd
import config
import utils
import lux_algo
import risk_manager
import state
from execution import HyperliquidClient
import threading
import logging

logger = logging.getLogger(__name__)

# Reconciliation lock to prevent overlapping runs
_reconciliation_lock = threading.Lock()

def prepare_dataframe(ohlcv):
    """Converts CCXT OHLCV list to DataFrame."""
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    return df

def format_order_params(client, symbol, params):
    """Format order parameters with proper precision."""
    qty = client.exchange.amount_to_precision(symbol, params['quantity'])
    entry_price = client.exchange.price_to_precision(symbol, params['entry_price'])
    sl_price = client.exchange.price_to_precision(symbol, params['stop_loss'])
    tp_price = client.exchange.price_to_precision(symbol, params['take_profit'])
    return {
        'quantity': qty,
        'entry_price': entry_price,
        'stop_loss': sl_price,
        'take_profit': tp_price
    }

def update_exchange_orders_count(client):
    """Update the count of open orders on the exchange.
    
    This function fetches all open orders from the exchange and updates
    the metrics to reflect the current count. This ensures the frontend
    displays accurate "Exchange Orders" count.
    
    Args:
        client: HyperliquidClient instance for fetching orders
        
    Returns:
        None
        
    Note:
        Handles exceptions gracefully - partial failures for individual symbols
        don't prevent updating the count. Network errors or API rate limits are
        caught and logged, allowing the function to continue processing remaining symbols.
    """
    try:
        symbols = utils.get_trading_pairs()
        all_orders = []
        
        for symbol in symbols:
            try:
                orders = client.get_open_orders(symbol)
                all_orders.extend(orders)
            except Exception as e:
                print(f"Error fetching orders for {symbol} in count update: {e}")
        
        # Update the metric with the count of successfully fetched orders
        state.bot_state.metrics.open_exchange_orders_count = len(all_orders)
    except Exception as e:
        print(f"Error updating exchange orders count: {e}")

def reconcile_live_orders(client):
    """Reconcile exchange orders with persisted pending orders at startup.
    
    This function:
    1. Fetches all open orders from the exchange
    2. Matches them with persisted pending orders
    3. Adds unmatched orders that align with current OBs
    4. Cancels unmatched orders that don't align with strategy
    """
    print("\n=== Starting Order Reconciliation ===")
    state.add_reconciliation_log("reconciliation_start", {"message": "Starting order reconciliation"})
    
    symbols = utils.get_trading_pairs()
    all_exchange_orders = []
    
    # Fetch open orders for all symbols
    for symbol in symbols:
        try:
            orders = client.get_open_orders(symbol)
            all_exchange_orders.extend(orders)
        except Exception as e:
            print(f"Error fetching orders for {symbol}: {e}")
    
    print(f"Found {len(all_exchange_orders)} open orders on exchange")
    state.bot_state.metrics.open_exchange_orders_count = len(all_exchange_orders)
    
    # Track matched order IDs
    matched_order_ids = set()
    
    # Match exchange orders with pending orders
    for order in all_exchange_orders:
        order_id = order.get('id')
        symbol = order.get('symbol')
        order_type = order.get('type', '')
        
        # Check if it's a TP/SL order (reduceOnly)
        is_tp_sl = order.get('reduceOnly', False) or order_type in ['STOP_MARKET', 'TAKE_PROFIT_MARKET']
        
        # Check if matches a pending order
        pending = state.get_pending_order(symbol)
        if pending and pending.get('order_id') == order_id:
            matched_order_ids.add(order_id)
            print(f"✓ Matched order {order_id} for {symbol} with pending order")
            state.add_reconciliation_log("order_matched", {
                "order_id": order_id,
                "symbol": symbol,
                "message": "Exchange order matched with pending order"
            })
            continue
        
        # If not matched and not TP/SL, try to match with current OBs
        if not is_tp_sl:
            print(f"Found unmatched limit order {order_id} for {symbol}")
            
            # Fetch current OHLCV and detect OBs
            try:
                ohlcv = client.fetch_ohlcv(symbol)
                if ohlcv:
                    df = prepare_dataframe(ohlcv)
                    obs = lux_algo.detect_order_blocks(df)
                    
                    order_price = float(order.get('price', 0))
                    order_side = order.get('side', '').lower()
                    
                    # Try to match with an OB (0.5% tolerance)
                    matched_ob = False
                    for ob in obs:
                        tolerance = 0.005  # 0.5% tolerance
                        if ob['type'] == 'bullish' and order_side == 'buy':
                            # Check if order price is near OB top
                            if abs(order_price - ob['ob_top']) / ob['ob_top'] < tolerance:
                                matched_ob = True
                                break
                        elif ob['type'] == 'bearish' and order_side == 'sell':
                            # Check if order price is near OB bottom
                            if abs(order_price - ob['ob_bottom']) / ob['ob_bottom'] < tolerance:
                                matched_ob = True
                                break
                    
                    if matched_ob:
                        # Add to pending orders
                        print(f"✓ Order {order_id} matches active OB, adding to tracking")
                        state.add_pending_order(symbol, order_id, {
                            'side': order_side,
                            'quantity': float(order.get('amount', 0)),
                            'entry_price': order_price,
                            'stop_loss': 0,  # Will be set when filled
                            'take_profit': 0,  # Will be set when filled
                            'reconciled': True
                        })
                        state.add_reconciliation_log("order_added_from_ob", {
                            "order_id": order_id,
                            "symbol": symbol,
                            "message": "Exchange order matched with active OB and added to tracking"
                        })
                        matched_order_ids.add(order_id)
                    else:
                        # Cancel unmatched order
                        print(f"✗ Order {order_id} doesn't match any OB, canceling...")
                        try:
                            client.exchange.cancel_order(order_id, symbol)
                            print(f"Cancelled orphaned order {order_id}")
                            state.bot_state.metrics.cancelled_orders_count += 1
                            state.save_metrics()
                            state.add_reconciliation_log("order_cancelled", {
                                "order_id": order_id,
                                "symbol": symbol,
                                "reason": "No matching OB found"
                            })
                        except Exception as e:
                            print(f"Failed to cancel order {order_id}: {e}")
            except Exception as e:
                print(f"Error reconciling order {order_id}: {e}")
        else:
            # TP/SL orders are fine, just log them
            matched_order_ids.add(order_id)
            print(f"✓ Found TP/SL order {order_id} for {symbol}")
            state.add_reconciliation_log("tp_sl_found", {
                "order_id": order_id,
                "symbol": symbol,
                "message": "TP/SL order found on exchange"
            })
    
    # Check for orphaned pending orders (in state but not on exchange)
    orphaned_symbols = []
    for symbol, pending in list(state.bot_state.pending_orders.items()):
        order_id = pending.get('order_id')
        if order_id not in matched_order_ids:
            print(f"⚠ Pending order {order_id} for {symbol} not found on exchange")
            # Try to fetch order status
            try:
                order_status = client.get_order_status(symbol, order_id)
                if order_status:
                    status = order_status.get('status')
                    if status in ['filled', 'canceled', 'expired', 'rejected']:
                        print(f"Order {order_id} is {status}, removing from pending")
                        orphaned_symbols.append(symbol)
                        state.add_reconciliation_log("orphaned_order_resolved", {
                            "order_id": order_id,
                            "symbol": symbol,
                            "status": status,
                            "message": f"Orphaned order found with status {status}"
                        })
                        if status == 'filled':
                            state.bot_state.metrics.filled_orders_count += 1
                            state.save_metrics()
                else:
                    print(f"Order {order_id} not found, removing from pending")
                    orphaned_symbols.append(symbol)
                    state.add_reconciliation_log("orphaned_order_removed", {
                        "order_id": order_id,
                        "symbol": symbol,
                        "message": "Orphaned order not found on exchange, removed"
                    })
            except Exception as e:
                print(f"Error checking orphaned order {order_id}: {e}")
                orphaned_symbols.append(symbol)
    
    # Remove orphaned orders
    for symbol in orphaned_symbols:
        state.remove_pending_order(symbol)
    
    print(f"=== Reconciliation Complete: {len(matched_order_ids)} orders matched, {len(orphaned_symbols)} orphaned ===\n")
    state.add_reconciliation_log("reconciliation_complete", {
        "matched_orders": len(matched_order_ids),
        "orphaned_orders": len(orphaned_symbols),
        "message": "Order reconciliation completed"
    })

def reconcile_position_tp_sl(client, symbol, position, pending_order=None):
    """Reconcile TP/SL orders for an open position.
    
    This function:
    1. Checks if position has TP/SL orders
    2. Verifies TP/SL quantities match position size
    3. Places missing TP/SL orders or replaces mismatched ones
    
    Args:
        client: HyperliquidClient instance
        symbol: Trading symbol
        position: Position dict from exchange
        pending_order: Optional pending order data with TP/SL params
        
    Returns:
        bool: True if reconciliation successful, False otherwise
    """
    try:
        # Get position details
        position_amount = float(position.get('contracts', position.get('positionAmt', 0)) or 0)
        if position_amount == 0:
            return True  # No position, nothing to reconcile
        
        position_size = abs(position_amount)
        is_long = position_amount > 0
        side = 'LONG' if is_long else 'SHORT'
        entry_price = float(position.get('entryPrice', 0) or 0)
        
        print(f"\n--- Reconciling TP/SL for {symbol} ({side}) ---")
        print(f"Position size: {position_size}, Entry: {entry_price}")
        
        # Get existing TP/SL orders
        tp_sl_orders = client.get_tp_sl_orders_for_position(symbol)
        sl_order = tp_sl_orders['sl_order']
        tp_order = tp_sl_orders['tp_order']
        
        # Determine TP/SL prices
        sl_price = None
        tp_price = None
        
        # Try to get TP/SL from pending order first
        if pending_order and pending_order.get('params'):
            params = pending_order['params']
            sl_price = params.get('stop_loss')
            tp_price = params.get('take_profit')
            if sl_price:
                sl_price = float(client.exchange.price_to_precision(symbol, sl_price))
            if tp_price:
                tp_price = float(client.exchange.price_to_precision(symbol, tp_price))
        
        # If no pending order, calculate TP/SL based on position
        if not sl_price or not tp_price:
            # Use simple percentage-based TP/SL as fallback
            risk_pct = 0.01  # 1% risk
            rr_ratio = config.RR_RATIO
            
            if is_long:
                sl_price = entry_price * (1 - risk_pct)
                tp_price = entry_price * (1 + risk_pct * rr_ratio)
            else:
                sl_price = entry_price * (1 + risk_pct)
                tp_price = entry_price * (1 - risk_pct * rr_ratio)
            
            sl_price = float(client.exchange.price_to_precision(symbol, sl_price))
            tp_price = float(client.exchange.price_to_precision(symbol, tp_price))
            print(f"Calculated TP/SL from position: SL={sl_price}, TP={tp_price}")
        
        # Determine close side (opposite of position)
        close_side = 'sell' if is_long else 'buy'
        
        # Format position size with proper precision
        formatted_size = float(client.exchange.amount_to_precision(symbol, position_size))
        
        # Check if TP/SL orders need to be placed or replaced
        needs_sl = False
        needs_tp = False
        
        if not sl_order:
            print(f"⚠ Missing SL order for {symbol}")
            needs_sl = True
            state.add_reconciliation_log("missing_sl_detected", {
                "symbol": symbol,
                "position_size": position_size,
                "message": f"Position exists without SL order"
            })
        else:
            sl_amount = float(sl_order.get('amount', 0))
            if abs(sl_amount - formatted_size) > formatted_size * config.TP_SL_QUANTITY_TOLERANCE:
                print(f"⚠ SL quantity mismatch for {symbol}: {sl_amount} vs {formatted_size}")
                needs_sl = True
                # Cancel existing SL
                client.cancel_order(symbol, sl_order['id'])
                state.add_reconciliation_log("sl_quantity_mismatch", {
                    "symbol": symbol,
                    "expected": formatted_size,
                    "actual": sl_amount,
                    "message": f"SL order quantity mismatch, cancelling"
                })
        
        if not tp_order:
            print(f"⚠ Missing TP order for {symbol}")
            needs_tp = True
            state.add_reconciliation_log("missing_tp_detected", {
                "symbol": symbol,
                "position_size": position_size,
                "message": f"Position exists without TP order"
            })
        else:
            tp_amount = float(tp_order.get('amount', 0))
            if abs(tp_amount - formatted_size) > formatted_size * config.TP_SL_QUANTITY_TOLERANCE:
                print(f"⚠ TP quantity mismatch for {symbol}: {tp_amount} vs {formatted_size}")
                needs_tp = True
                # Cancel existing TP
                client.cancel_order(symbol, tp_order['id'])
                state.add_reconciliation_log("tp_quantity_mismatch", {
                    "symbol": symbol,
                    "expected": formatted_size,
                    "actual": tp_amount,
                    "message": f"TP order quantity mismatch, cancelling"
                })
        
        # Place missing or replacement orders
        if needs_sl or needs_tp:
            # Safety check: If we have a pending order with recent TP/SL placement,
            # wait a bit before trying again to let the exchange API reflect the new orders.
            # This helps prevent duplicate orders when the API response lags.
            if pending_order and pending_order.get('last_tp_sl_placement'):
                import datetime as dt
                try:
                    last_placement_str = pending_order.get('last_tp_sl_placement')
                    last_placement = dt.datetime.fromisoformat(last_placement_str)
                    seconds_since_placement = (dt.datetime.now() - last_placement).total_seconds()
                    
                    # If orders were placed within the last 30 seconds, skip this cycle
                    # to allow the exchange API to reflect the changes
                    if seconds_since_placement < 30:
                        logger.info("Skipping TP/SL placement for %s - orders placed %.1f seconds ago, "
                                   "waiting for API to sync", symbol, seconds_since_placement)
                        state.add_reconciliation_log("tp_sl_placement_deferred", {
                            "symbol": symbol,
                            "seconds_since_placement": seconds_since_placement,
                            "message": f"Deferring TP/SL placement - waiting for API sync"
                        })
                        return True  # Return success to avoid repeated attempts
                except (ValueError, TypeError) as e:
                    logger.debug("Could not parse last_tp_sl_placement for %s: %s", symbol, e)
            
            print(f"Placing TP/SL orders for {symbol}...")
            if needs_sl and needs_tp:
                # Place both together
                orders = client.place_sl_tp_orders(symbol, 'buy' if is_long else 'sell', 
                                                  formatted_size, sl_price, tp_price)
                if orders['sl_order'] and orders['tp_order']:
                    if pending_order:
                        state.update_pending_order_exchange_orders(symbol, orders['sl_order'], orders['tp_order'])
                    print(f"✓ Successfully placed both TP and SL for {symbol}")
                    state.add_reconciliation_log("tp_sl_placed", {
                        "symbol": symbol,
                        "sl_price": sl_price,
                        "tp_price": tp_price,
                        "size": formatted_size,
                        "message": "TP/SL orders successfully placed"
                    })
                    return True
                else:
                    print(f"✗ Failed to place some TP/SL orders for {symbol}")
                    return False
            elif needs_sl:
                # Place only SL
                sl_order_result = client.place_stop_loss(symbol, close_side, formatted_size, sl_price)
                if sl_order_result:
                    print(f"✓ Successfully placed SL for {symbol}")
                    state.add_reconciliation_log("sl_placed", {
                        "symbol": symbol,
                        "sl_price": sl_price,
                        "size": formatted_size,
                        "message": "SL order successfully placed"
                    })
                    return True
                else:
                    print(f"✗ Failed to place SL for {symbol}")
                    return False
            elif needs_tp:
                # Place only TP
                tp_order_result = client.place_take_profit(symbol, close_side, formatted_size, tp_price)
                if tp_order_result:
                    print(f"✓ Successfully placed TP for {symbol}")
                    state.add_reconciliation_log("tp_placed", {
                        "symbol": symbol,
                        "tp_price": tp_price,
                        "size": formatted_size,
                        "message": "TP order successfully placed"
                    })
                    return True
                else:
                    print(f"✗ Failed to place TP for {symbol}")
                    return False
        else:
            print(f"✓ TP/SL orders are correct for {symbol}")
            return True
            
    except Exception as e:
        print(f"Error reconciling TP/SL for {symbol}: {e}")
        state.add_reconciliation_log("reconciliation_error", {
            "symbol": symbol,
            "error": str(e),
            "message": f"Error during TP/SL reconciliation"
        })
        return False

def reconcile_existing_positions_with_trades(client):
    """Reconcile existing open positions with trade history.
    
    When the bot starts, there may be open positions from previous runs
    that don't have corresponding entries in trade history. This function
    creates those entries so the positions are properly tracked.
    
    Args:
        client: HyperliquidClient instance
    """
    print("\n=== Reconciling Existing Positions with Trade History ===")
    
    try:
        # Fetch all open positions from exchange
        positions = client.get_all_positions()
        print(f"Found {len(positions)} open positions on exchange")
        
        for position in positions:
            symbol = position.get('symbol')
            if not symbol:
                continue
            
            # Check if there's already an open trade for this symbol
            has_open_trade = any(
                t.get('symbol') == symbol and t.get('status') == 'OPEN'
                for t in state.bot_state.trade_history
            )
            
            if not has_open_trade:
                # Create a trade entry for this position
                try:
                    position_amount = float(position.get('contracts', position.get('positionAmt', 0)) or 0)
                    if position_amount == 0:
                        continue
                    
                    entry_price = float(position.get('entryPrice', 0) or 0)
                except (ValueError, TypeError) as e:
                    print(f"WARNING: Invalid position data for {symbol}: {e}")
                    continue
                side = 'LONG' if position_amount > 0 else 'SHORT'
                
                print(f"Creating trade entry for existing position: {symbol} {side}")
                
                # Get TP/SL from open orders if available
                tp_sl_orders = client.get_tp_sl_orders_for_position(symbol)
                tp_price = None
                sl_price = None
                
                if tp_sl_orders and tp_sl_orders.get('tp_order'):
                    tp_price = float(tp_sl_orders['tp_order'].get('stopPrice', 0) or 0)
                if tp_sl_orders and tp_sl_orders.get('sl_order'):
                    sl_price = float(tp_sl_orders['sl_order'].get('stopPrice', 0) or 0)
                
                state.add_trade({
                    'symbol': symbol,
                    'side': side,
                    'entry_price': entry_price,
                    'exit_price': None,
                    'size': abs(position_amount),
                    'pnl': None,
                    'status': 'OPEN',
                    'take_profit': tp_price,
                    'stop_loss': sl_price,
                    'entry_time': None  # Unknown for existing positions
                })
                print(f"✓ Trade entry created for {symbol}")
        
        print(f"=== Position-Trade Reconciliation Complete ===\n")
        
    except Exception as e:
        print(f"Error reconciling positions with trades: {e}")

def reconcile_all_positions_tp_sl(client):
    """Reconcile TP/SL orders for all open positions.
    
    This function is called at startup and periodically to ensure
    all positions have proper TP/SL orders.
    
    Uses a lock to prevent overlapping reconciliation runs.
    
    Args:
        client: HyperliquidClient instance
    """
    # Try to acquire the lock without blocking
    if not _reconciliation_lock.acquire(blocking=False):
        logger.debug("Reconciliation already running - skipping this cycle")
        state.bot_state.metrics.reconciliation_skipped_count += 1
        state.add_reconciliation_log("reconciliation_skipped", {
            "message": "Reconciliation already running, skipped this cycle"
        })
        return
    
    try:
        state.bot_state.metrics.reconciliation_runs_count += 1
        print("\n=== Starting Position TP/SL Reconciliation ===")
        state.add_reconciliation_log("position_reconciliation_start", {
            "message": "Starting position TP/SL reconciliation"
        })
        
        # Fetch all open positions
        positions = client.get_all_positions()
        print(f"Found {len(positions)} open positions")
        
        reconciled_count = 0
        failed_count = 0
        
        for position in positions:
            symbol = position.get('symbol')
            if not symbol:
                continue
            
            # Update position in state to ensure it's tracked
            state.update_position(symbol, position)
            
            # Check if there's a pending order for this symbol
            pending = state.get_pending_order(symbol)
            
            # Reconcile this position
            success = reconcile_position_tp_sl(client, symbol, position, pending)
            if success:
                reconciled_count += 1
            else:
                failed_count += 1
        
        print(f"=== Position Reconciliation Complete: {reconciled_count} reconciled, {failed_count} failed ===\n")
        state.add_reconciliation_log("position_reconciliation_complete", {
            "reconciled": reconciled_count,
            "failed": failed_count,
            "message": "Position TP/SL reconciliation completed"
        })
        
    except Exception as e:
        print(f"Error in position reconciliation: {e}")
        state.add_reconciliation_log("position_reconciliation_error", {
            "error": str(e),
            "message": "Error during position TP/SL reconciliation"
        })
    finally:
        _reconciliation_lock.release()

def monitor_and_close_positions(client):
    """Monitor open positions and force-close them if TP/SL levels are breached.
    
    This function acts as a safety net to close positions when:
    - TP/SL conditional orders are missing or cancelled
    - TP/SL conditional orders fail to execute
    - Price breaches TP/SL levels but orders don't trigger
    
    Args:
        client: HyperliquidClient instance
    """
    if not config.ENABLE_ACTIVE_TP_SL_MONITORING:
        return
    
    try:
        # Get all symbols with open positions
        position_symbols = list(state.bot_state.positions.keys())
        
        if not position_symbols:
            return  # No positions to monitor
        
        for symbol in position_symbols:
            try:
                position = state.bot_state.positions.get(symbol)
                if not position:
                    continue
                
                # Extract position details
                size = position.get('size', 0)
                side = position.get('side', '').upper()
                mark_price = position.get('mark_price', 0)
                take_profit = position.get('take_profit')
                stop_loss = position.get('stop_loss')
                entry_price = position.get('entry_price', 0)
                
                # Skip if position size is 0 or invalid data
                if size <= 0 or mark_price <= 0:
                    continue
                
                # Skip if no TP/SL values are available
                if not take_profit and not stop_loss:
                    continue
                
                # Determine if position should be closed
                should_close = False
                close_reason = None
                
                if side == 'LONG':
                    # For LONG positions:
                    # Close if price >= TP (take profit hit)
                    # Close if price <= SL (stop loss hit)
                    if take_profit and mark_price >= take_profit:
                        should_close = True
                        close_reason = "tp_breach"
                    elif stop_loss and mark_price <= stop_loss:
                        should_close = True
                        close_reason = "sl_breach"
                elif side == 'SHORT':
                    # For SHORT positions:
                    # Close if price <= TP (take profit hit)
                    # Close if price >= SL (stop loss hit)
                    if take_profit and mark_price <= take_profit:
                        should_close = True
                        close_reason = "tp_breach"
                    elif stop_loss and mark_price >= stop_loss:
                        should_close = True
                        close_reason = "sl_breach"
                
                # If breach detected, force close the position
                if should_close and close_reason:
                    print(f"\n⚠️ BREACH DETECTED for {symbol}!")
                    print(f"Position: {side}, Mark Price: {mark_price}, Entry: {entry_price}")
                    print(f"TP: {take_profit}, SL: {stop_loss}")
                    print(f"Reason: {close_reason}")
                    
                    # Determine close side (opposite of position)
                    close_side = 'sell' if side == 'LONG' else 'buy'
                    
                    # Format size with proper precision
                    formatted_size = float(client.exchange.amount_to_precision(symbol, size))
                    
                    # Cancel existing TP/SL orders first
                    tp_sl_orders = client.get_tp_sl_orders_for_position(symbol)
                    cancelled_orders = []
                    if tp_sl_orders.get('sl_order'):
                        if client.cancel_order(symbol, tp_sl_orders['sl_order']['id']):
                            cancelled_orders.append('SL')
                    if tp_sl_orders.get('tp_order'):
                        if client.cancel_order(symbol, tp_sl_orders['tp_order']['id']):
                            cancelled_orders.append('TP')
                    
                    # Close position with market order
                    market_order = client.close_position_market(symbol, close_side, formatted_size, close_reason)
                    
                    if market_order:
                        # Calculate PnL for logging
                        if side == 'LONG':
                            pnl = (mark_price - entry_price) * size
                        else:
                            pnl = (entry_price - mark_price) * size
                        
                        # Log the forced closure
                        state.add_forced_closure_log(symbol, close_reason, {
                            'side': side,
                            'size': size,
                            'entry_price': entry_price,
                            'mark_price': mark_price,
                            'take_profit': take_profit,
                            'stop_loss': stop_loss,
                            'pnl': round(pnl, 2),
                            'cancelled_orders': cancelled_orders,
                            'market_order_id': market_order.get('id')
                        })
                        
                        print(f"✓ Position closed successfully. Estimated PnL: {pnl:.2f} USDC")
                        
                        # Update trade history
                        # The position update will handle closing the trade when we fetch positions again
                        
                        # Small delay to avoid rate limits
                        time.sleep(config.FORCED_CLOSURE_RATE_LIMIT_DELAY)
                    else:
                        print(f"✗ Failed to close position for {symbol}")
                        state.add_reconciliation_log("forced_closure_failed", {
                            'symbol': symbol,
                            'reason': close_reason,
                            'message': 'Market order failed to execute'
                        })
                
            except Exception as e:
                print(f"Error monitoring position for {symbol}: {e}")
                state.add_reconciliation_log("monitor_error", {
                    'symbol': symbol,
                    'error': str(e),
                    'message': 'Error during position monitoring'
                })
                # Continue monitoring other positions
                continue
        
    except Exception as e:
        print(f"Error in monitor_and_close_positions: {e}")
        state.add_reconciliation_log("monitor_error", {
            'error': str(e),
            'message': 'Top-level error in position monitoring'
        })

def handle_stale_pending_orders(client):
    """Check for and handle stale pending orders.
    
    Orders that have been pending for longer than PENDING_ORDER_STALE_SECONDS
    are considered stale. This function cancels them and removes from tracking.
    
    Args:
        client: HyperliquidClient instance
    """
    stale_orders = state.get_stale_pending_orders(config.PENDING_ORDER_STALE_SECONDS)
    
    if not stale_orders:
        return
    
    print(f"\n=== Found {len(stale_orders)} stale pending orders ===")
    
    for symbol, pending in stale_orders.items():
        order_id = pending.get('order_id')
        age_seconds = pending.get('age_seconds', 0)
        
        logger.info("Stale pending order detected: symbol=%s order_id=%s age_seconds=%.0f",
                   symbol, order_id, age_seconds)
        
        try:
            # Try to cancel the order on the exchange
            cancelled = client.cancel_order(symbol, order_id)
            
            if cancelled:
                print(f"Cancelled stale order {order_id} for {symbol} (age: {age_seconds:.0f}s)")
                state.bot_state.metrics.pending_order_stale_count += 1
                state.bot_state.metrics.cancelled_orders_count += 1
                state.add_reconciliation_log("stale_order_cancelled", {
                    "symbol": symbol,
                    "order_id": order_id,
                    "age_seconds": age_seconds,
                    "message": f"Stale pending order cancelled after {age_seconds:.0f}s"
                })
            else:
                # Order may already be gone, just log it
                print(f"Could not cancel stale order {order_id} for {symbol} (may already be filled/cancelled)")
                state.add_reconciliation_log("stale_order_removal", {
                    "symbol": symbol,
                    "order_id": order_id,
                    "age_seconds": age_seconds,
                    "message": "Stale order removed from tracking (cancel failed)"
                })
            
            # Remove from pending orders regardless
            state.remove_pending_order(symbol)
            
        except Exception as e:
            logger.warning("Error handling stale order %s for %s: %s", order_id, symbol, e)
            # Remove from pending orders to prevent repeated errors
            state.remove_pending_order(symbol)
            state.add_reconciliation_log("stale_order_error", {
                "symbol": symbol,
                "order_id": order_id,
                "error": str(e),
                "message": "Error handling stale order, removed from tracking"
            })
    
    state.save_metrics()

def run_bot_logic():
    print("Starting LuxAlgo Order Block Bot Logic...")
    
    # Initialize state and load persisted data
    state.init()
    
    client = HyperliquidClient()
    
    # Reconcile live orders before starting main loop
    reconcile_live_orders(client)
    
    # Reconcile positions and their TP/SL orders at startup
    reconcile_all_positions_tp_sl(client)
    
    # Reconcile existing positions with trade history
    reconcile_existing_positions_with_trades(client)
    
    # Track last reconciliation time
    import time as time_module
    last_position_reconciliation = time_module.time()
    
    while True:
        try:
            # Check if it's time for periodic position reconciliation
            current_time = time_module.time()
            if current_time - last_position_reconciliation > config.POSITION_RECONCILIATION_INTERVAL:
                print("\n--- Periodic Position Reconciliation ---")
                reconcile_all_positions_tp_sl(client)
                # Also check for stale pending orders
                handle_stale_pending_orders(client)
                last_position_reconciliation = current_time
            
            # 1. Check and process any pending orders first
            for symbol in list(state.bot_state.pending_orders.keys()):
                pending = state.get_pending_order(symbol)
                if pending:
                    order_status = client.get_order_status(symbol, pending['order_id'])
                    if order_status:
                        original_amount = float(order_status.get('amount', 0))
                        filled_amount = float(order_status.get('filled', 0))
                        remaining_amount = original_amount - filled_amount
                        
                        # Check if order is fully filled
                        if order_status.get('status') == 'filled':
                            print(f"Limit order filled for {symbol}. Placing TP/SL orders...")
                            params = pending['params']
                            
                            # Format prices with proper precision
                            formatted = format_order_params(client, symbol, params)
                            
                            # Place TP and SL orders
                            orders = client.place_sl_tp_orders(
                                symbol, params['side'], 
                                formatted['quantity'],
                                formatted['stop_loss'],
                                formatted['take_profit']
                            )
                            
                            if orders['sl_order'] and orders['tp_order']:
                                print(f"TP/SL orders successfully placed for {symbol}")
                                state.update_pending_order_exchange_orders(symbol, orders['sl_order'], orders['tp_order'])
                                state.bot_state.metrics.filled_orders_count += 1
                                state.save_metrics()
                            else:
                                print(f"WARNING: Some TP/SL orders failed for {symbol}")
                            
                            # Record the trade entry using actual fill price from order status
                            # Use average fill price if available, otherwise fall back to order price
                            fill_price = float(order_status.get('average', order_status.get('price', params['entry_price'])))
                            quantity = float(formatted['quantity'])
                            state.add_trade({
                                'symbol': symbol,
                                'side': params['side'].upper(),
                                'entry_price': fill_price,
                                'exit_price': None,
                                'size': quantity,
                                'pnl': None,
                                'status': 'OPEN',
                                'take_profit': float(formatted['take_profit']),
                                'stop_loss': float(formatted['stop_loss']),
                                'entry_time': order_status.get('datetime', None)
                            })
                            print(f"Trade entry recorded for {symbol}")
                            
                            # Remove from pending orders
                            state.remove_pending_order(symbol)
                            
                        # Handle partial fills
                        elif filled_amount > 0 and remaining_amount > 0:
                            print(f"Partial fill detected for {symbol}: {filled_amount}/{original_amount} filled")
                            params = pending['params']
                            
                            # Place TP/SL for filled portion
                            filled_qty = client.exchange.amount_to_precision(symbol, filled_amount)
                            formatted = format_order_params(client, symbol, params)
                            
                            orders = client.place_sl_tp_orders(
                                symbol, params['side'],
                                filled_qty,
                                formatted['stop_loss'],
                                formatted['take_profit']
                            )
                            
                            if orders['sl_order'] and orders['tp_order']:
                                print(f"TP/SL placed for partial fill: {filled_qty}")
                                state.update_pending_order_exchange_orders(symbol, orders['sl_order'], orders['tp_order'])
                            
                            # Update pending order with remaining quantity
                            pending['params']['quantity'] = remaining_amount
                            pending['partial_fill'] = True
                            pending['filled_amount'] = filled_amount
                            state.bot_state.pending_orders[symbol] = pending
                            state.save_pending_orders()
                            print(f"Updated pending order with remaining quantity: {remaining_amount}")
                            
                        elif order_status.get('status') in ['canceled', 'expired', 'rejected']:
                            print(f"Limit order {order_status.get('status')} for {symbol}. Removing from pending.")
                            if order_status.get('status') == 'canceled':
                                state.bot_state.metrics.cancelled_orders_count += 1
                                state.save_metrics()
                            state.remove_pending_order(symbol)
            
            # 2. Fetch Trading Pairs
            symbols = utils.get_trading_pairs()
            # print(f"\nScanning {len(symbols)} pairs: {symbols}")
            
            # Fetch full balance info
            full_balance = client.get_full_balance()
            state.update_full_balance(full_balance['total'], full_balance['free'], full_balance['used'])
            # print(f"Current Balance: {full_balance['total']:.2f} USDC (Free: {full_balance['free']:.2f})")
            
            # Fetch all open orders from exchange and update state
            exchange_orders = client.get_all_open_orders()
            state.update_exchange_open_orders(exchange_orders)
            
            # Enrich positions with TP/SL derived from exchange orders
            state.enrich_positions_with_tp_sl()
            
            # Monitor and force-close positions if TP/SL breached
            monitor_and_close_positions(client)
            
            for symbol in symbols:
                # print(f"\n--- Processing {symbol} ---")
                
                # Check current position
                position = client.get_position(symbol)
                state.update_position(symbol, position)
                
                # 2. Fetch Data
                ohlcv = client.fetch_ohlcv(symbol)
                if not ohlcv:
                    continue
                    
                df = prepare_dataframe(ohlcv)
                
                # Update State for Frontend Chart
                state.update_ohlcv(symbol, df)
                
                # 3. Detect Order Blocks
                obs = lux_algo.detect_order_blocks(df)
                
                # Update State for Frontend OBs
                # We want to serialize OBs for the frontend
                # Convert timestamps to ISO string or Unix ms
                serializable_obs = []
                for ob in obs:
                    ob_copy = ob.copy()
                    ob_copy['time'] = int(ob['time'].timestamp()) # Unix
                    # confirm_index is internal, maybe not needed for frontend
                    serializable_obs.append(ob_copy)
                state.update_order_blocks(symbol, serializable_obs)

                if not obs:
                    # print("No valid unmitigated order blocks found.")
                    continue
                
                # Check if position exists using ccxt unified format
                # ccxt uses 'contracts' for position amount, 'entryPrice' for entry price
                has_position = False
                if position:
                    contracts = position.get('contracts', position.get('positionAmt', 0))
                    if contracts is None:
                        contracts = 0
                    entry_price = position.get('entryPrice', 0)
                    if entry_price is None:
                        entry_price = 0
                    has_position = float(contracts) != 0 and float(entry_price) > 0
                
                if has_position:
                    # print(f"Position exists for {symbol}. Skipping new entry search.")
                    continue
                    
                # 4. Select Best OB
                current_price = df['close'].iloc[-1]
                
                valid_candidates = []
                for ob in obs:
                    if ob['type'] == 'bullish' and current_price > ob['ob_top']:
                        dist = abs(current_price - ob['ob_top'])
                        ob['distance'] = dist
                        valid_candidates.append(ob)
                    elif ob['type'] == 'bearish' and current_price < ob['ob_bottom']:
                        dist = abs(current_price - ob['ob_bottom'])
                        ob['distance'] = dist
                        valid_candidates.append(ob)
                        
                if not valid_candidates:
                    continue
                    
                # Sort by distance
                valid_candidates.sort(key=lambda x: x['distance'])
                best_ob = valid_candidates[0]
                
                # print(f"Found Candidate OB: {best_ob['type'].upper()} at {best_ob['ob_top']}-{best_ob['ob_bottom']}")
                
                # 5. Calculate Parameters
                params = risk_manager.calculate_trade_params(best_ob, full_balance['free'])
                if not params:
                    continue
                params['symbol'] = symbol
                
                # 6. Check if pending order exists and verify it's still on exchange
                pending = state.get_pending_order(symbol)
                if pending:
                    # Verify the order still exists on exchange
                    pending_order_id = pending.get('order_id')
                    try:
                        order_status = client.get_order_status(symbol, pending_order_id)
                        if order_status and order_status.get('status') == 'open':
                            # Order still exists on exchange, skip new placement
                            # Only log if this is a new detection to reduce noise
                            if state.should_log_pending_order_still_active(symbol, pending_order_id):
                                print(f"Pending order {pending_order_id} still active for {symbol}, skipping new placement")
                                state.add_reconciliation_log("placement_skipped", {
                                    "symbol": symbol,
                                    "order_id": pending_order_id,
                                    "reason": "Pending order still active on exchange"
                                })
                            continue
                        else:
                            # Order was cancelled or filled, remove from pending
                            status = order_status.get('status', 'not found') if order_status else 'not found'
                            print(f"Pending order {pending_order_id} for {symbol} is {status}, removing from tracking")
                            state.remove_pending_order(symbol)
                            state.add_reconciliation_log("pending_order_removed", {
                                "symbol": symbol,
                                "order_id": pending_order_id,
                                "status": status,
                                "message": "Pending order no longer active, removed from tracking"
                            })
                    except Exception as e:
                        # If we can't fetch the order, assume it was cancelled and remove from pending
                        print(f"Could not verify pending order {pending_order_id} for {symbol}: {e}")
                        print(f"Removing from pending orders to allow new placement")
                        state.remove_pending_order(symbol)
                        state.add_reconciliation_log("pending_order_removed", {
                            "symbol": symbol,
                            "order_id": pending_order_id,
                            "error": str(e),
                            "message": "Could not verify pending order, removed from tracking"
                        })
                
                # 7. Execute - cancel existing orders and place new limit order
                client.cancel_all_orders(symbol)
                
                # Format prices with proper precision
                formatted = format_order_params(client, symbol, params)
                
                print(f"Placing Order: {params['side']} {formatted['quantity']} @ {formatted['entry_price']}")
                order = client.place_limit_order(symbol, params['side'], formatted['quantity'], formatted['entry_price'])
                
                # Track the order and its TP/SL parameters
                if order and order.get('id'):
                    print(f"Order Placed ID: {order['id']}")
                    print(f"Tracking order for TP/SL placement once filled...")
                    
                    # Store the order info for later TP/SL placement
                    state.add_pending_order(symbol, order['id'], params)
                    state.bot_state.metrics.placed_orders_count += 1
                    state.save_metrics()
            
            # Note: exchange_orders count is already updated in state.update_exchange_open_orders() above
            
            # Sleep for 2 minutes between cycles
            time.sleep(120)
            
        except Exception as e:
            print(f"Top-level error: {e}")
            time.sleep(120)

def start_bot_thread():
    t = threading.Thread(target=run_bot_logic, daemon=True)
    t.start()
    return t

if __name__ == "__main__":
    run_bot_logic()
