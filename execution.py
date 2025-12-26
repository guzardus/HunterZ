import ccxt
import config

class BinanceClient:
    def __init__(self):
        self.exchange = ccxt.binance({
            'apiKey': config.API_KEY,
            'secret': config.API_SECRET,
            'options': {
                'defaultType': 'future'
            }
        })
        if config.BINANCE_TESTNET:
            self.exchange.set_sandbox_mode(True)
            print("Binance Testnet Enabled")

    def _resolve_symbol(self, symbol: str) -> str:
        """Resolve a configured symbol to the exact market symbol loaded by ccxt."""
        try:
            markets = self.exchange.markets or self.exchange.load_markets()
            if symbol in markets:
                return symbol
            if '/' in symbol:
                base, quote = symbol.split('/', 1)
                matches = [m for m in markets.values() if m.get('base') == base and m.get('quote') == quote]
                if matches:
                    resolved = matches[0].get('symbol', symbol)
                    if resolved != symbol:
                        print(f"Resolved symbol {symbol} -> {resolved}")
                    return resolved
        except Exception as e:
            print(f"Warning: could not resolve symbol {symbol}: {e}")
        return symbol

    def fetch_ohlcv(self, symbol, timeframe=config.TIMEFRAME, limit=100):
        try:
            resolved_symbol = self._resolve_symbol(symbol)
            ohlcv = self.exchange.fetch_ohlcv(resolved_symbol, timeframe, limit=limit)
            return ohlcv
        except Exception as e:
            print(f"Error fetching OHLCV for {symbol}: {e}")
            return []

    def get_balance(self):
        try:
            balance = self.exchange.fetch_balance()
            return balance['USDT']['free']
        except Exception as e:
            print(f"Error fetching balance: {e}")
            return 0.0

    def get_full_balance(self):
        """Get complete balance information including total, free, and used."""
        try:
            balance = self.exchange.fetch_balance()
            usdt_balance = balance.get('USDT', {})
            return {
                'total': float(usdt_balance.get('total', 0)),
                'free': float(usdt_balance.get('free', 0)),
                'used': float(usdt_balance.get('used', 0))
            }
        except Exception as e:
            print(f"Error fetching full balance: {e}")
            return {'total': 0.0, 'free': 0.0, 'used': 0.0}

    def get_position(self, symbol):
        try:
            resolved_symbol = self._resolve_symbol(symbol)
            positions = self.exchange.fetch_positions([resolved_symbol])
            for pos in positions:
                if pos.get('symbol') in (symbol, resolved_symbol):
                    # Preserve the exchange symbol while keeping the configured name for state
                    pos = pos.copy()
                    pos['exchange_symbol'] = pos.get('symbol', resolved_symbol)
                    pos['symbol'] = symbol
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
                    resolved_symbol = self._resolve_symbol(symbol)
                    symbol_orders = self.exchange.fetch_open_orders(resolved_symbol)
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
                resolved_symbol = self._resolve_symbol(symbol)
                trades = self.exchange.fetch_my_trades(resolved_symbol, limit=limit)
            else:
                # Fetch trades for all trading pairs
                all_trades = []
                for pair in config.TRADING_PAIRS:
                    try:
                        resolved_symbol = self._resolve_symbol(pair)
                        trades = self.exchange.fetch_my_trades(resolved_symbol, limit=10)
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
            resolved_symbol = self._resolve_symbol(symbol)
            self.exchange.cancel_all_orders(resolved_symbol)
            print(f"Cancelled all orders for {symbol}")
        except Exception as e:
            print(f"Error cancelling orders for {symbol}: {e}")

    def place_limit_order(self, symbol, side, amount, price):
        try:
            resolved_symbol = self._resolve_symbol(symbol)
            payload = {'symbol': resolved_symbol, 'type': 'limit', 'side': side, 'amount': amount, 'price': price}
            if config.BINANCE_TESTNET:
                print(f"Placing limit order payload: {payload}")
            order = self.exchange.create_order(resolved_symbol, 'limit', side, amount, price)
            print(f"Placed {side} limit order for {symbol} at {price}")
            return order
        except Exception as e:
            print(f"Error placing limit order for {symbol}: {e}")
            return None

    def place_stop_loss(self, symbol, side, amount, stop_price):
        try:
            resolved_symbol = self._resolve_symbol(symbol)
            # STOP_MARKET for Futures
            params = {'stopPrice': stop_price, 'reduceOnly': True}
            payload = {'symbol': resolved_symbol, 'side': side, 'amount': amount, 'params': params}
            if config.BINANCE_TESTNET:
                print(f"Placing Stop Loss payload: {payload}")
            order = self.exchange.create_order(resolved_symbol, 'STOP_MARKET', side, amount, params=params)
            print(f"Placed Stop Loss for {resolved_symbol} at {stop_price}")
            return order
        except Exception as e:
            print(f"Error placing SL for {symbol}: {e}")
            return None

    def place_take_profit(self, symbol, side, amount, tp_price):
        try:
            resolved_symbol = self._resolve_symbol(symbol)
            # TAKE_PROFIT_MARKET for Futures
            params = {'stopPrice': tp_price, 'reduceOnly': True}
            payload = {'symbol': resolved_symbol, 'side': side, 'amount': amount, 'params': params}
            if config.BINANCE_TESTNET:
                print(f"Placing Take Profit payload: {payload}")
            order = self.exchange.create_order(resolved_symbol, 'TAKE_PROFIT_MARKET', side, amount, params=params)
            print(f"Placed Take Profit for {resolved_symbol} at {tp_price}")
            return order
        except Exception as e:
            print(f"Error placing TP for {symbol}: {e}")
            return None

    def get_order_status(self, symbol, order_id):
        """Check the status of an order."""
        try:
            resolved_symbol = self._resolve_symbol(symbol)
            order = self.exchange.fetch_order(order_id, resolved_symbol)
            return order
        except Exception as e:
            print(f"Error fetching order status for {symbol}: {e}")
            return None

    def place_sl_tp_orders(self, symbol, side, amount, sl_price, tp_price):
        """Place both Stop Loss and Take Profit orders together."""
        sl_tp_side = 'sell' if side == 'buy' else 'buy'
        
        sl_order = self.place_stop_loss(symbol, sl_tp_side, amount, sl_price)
        tp_order = self.place_take_profit(symbol, sl_tp_side, amount, tp_price)
        
        return {'sl_order': sl_order, 'tp_order': tp_order}

    def get_open_orders(self, symbol=None):
        """Fetch open orders from the exchange.
        
        Args:
            symbol: Optional symbol to filter orders. If None, fetches all open orders.
            
        Returns:
            list: List of open orders
        """
        try:
            if symbol:
                resolved_symbol = self._resolve_symbol(symbol)
                orders = self.exchange.fetch_open_orders(resolved_symbol)
            else:
                orders = self.exchange.fetch_open_orders()
            return orders
        except Exception as e:
            print(f"Error fetching open orders for {symbol if symbol else 'all symbols'}: {e}")
            return []
    
    def get_tp_sl_orders_for_position(self, symbol):
        """Get TP/SL orders for a specific symbol.
        
        Args:
            symbol: Trading symbol to check for TP/SL orders
            
        Returns:
            dict: {'sl_order': order or None, 'tp_order': order or None}
        """
        try:
            resolved_symbol = self._resolve_symbol(symbol)
            orders = self.get_open_orders(resolved_symbol)
            sl_order = None
            tp_order = None
            
            for order in orders:
                order_symbol = order.get('symbol')
                if order_symbol not in (symbol, resolved_symbol):
                    continue
                order_type = order.get('type', '')
                is_reduce_only = order.get('reduceOnly', False)
                
                if is_reduce_only or order_type in ['STOP_MARKET', 'TAKE_PROFIT_MARKET', 
                                                     'stop_market', 'take_profit_market']:
                    if order_type in ['STOP_MARKET', 'stop_market']:
                        sl_order = order
                    elif order_type in ['TAKE_PROFIT_MARKET', 'take_profit_market']:
                        tp_order = order
            
            return {'sl_order': sl_order, 'tp_order': tp_order}
        except Exception as e:
            print(f"Error getting TP/SL orders for {symbol}: {e}")
            return {'sl_order': None, 'tp_order': None}
    
    def cancel_order(self, symbol, order_id):
        """Cancel a specific order.
        
        Args:
            symbol: Trading symbol
            order_id: Order ID to cancel
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            resolved_symbol = self._resolve_symbol(symbol)
            self.exchange.cancel_order(order_id, resolved_symbol)
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
        def _is_reduce_only_rejection(error):
            code = getattr(error, 'code', None) or getattr(error, 'errorCode', None)
            if code in (-2022, -2021):
                return True
            text = str(error).lower()
            body = getattr(error, 'body', '') or ''
            body = body.lower() if hasattr(body, 'lower') else ''
            indicators = (text, body)
            return any('reduceonly' in s or 'reduce only' in s or 'reduce_only' in s for s in indicators if s)

        try:
            # Create a MARKET order with reduceOnly=True
            params = {'reduceOnly': True}
            resolved_symbol = self._resolve_symbol(symbol)
            payload = {
                'symbol': resolved_symbol,
                'type': 'market',
                'side': side,
                'amount': amount,
                'params': params,
                'log_reason': reason
            }
            if config.BINANCE_TESTNET:
                print(f"Close attempt payload: {payload}")
            try:
                order = self.exchange.create_order(resolved_symbol, 'market', side, amount, params=params)
                print(f"⚠️ FORCED CLOSURE ({reason}): Closed {amount} {resolved_symbol} position with market {side} order")
                return order
            except Exception as inner:
                print(f"Primary close failed for {resolved_symbol}: {inner}.")
                if not _is_reduce_only_rejection(inner):
                    return None
                print("Retrying without reduceOnly...")
                fallback_params = {}
                order = self.exchange.create_order(resolved_symbol, 'market', side, amount, params=fallback_params)
                print(f"⚠️ FORCED CLOSURE ({reason}) without reduceOnly: Closed {amount} {resolved_symbol} with market {side}")
                return order
        except Exception as e:
            print(f"Error closing position for {symbol} with market order: {e}")
            return None
