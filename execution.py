import ccxt
import config

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
            try:
                return float(usdc_balance.get('free', 0))
            except (TypeError, ValueError):
                return 0.0
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
            orders = self.get_open_orders(symbol)
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
                except Exception as order_error:
                    failed += 1
                    print(f"Error cancelling order {order_id} for {symbol}: {order_error}")
            cancelled = len(orders) - failed - skipped
            print(f"Manually cancelled {cancelled} orders for {symbol} (failed: {failed}, skipped: {skipped})")
            return True
        except Exception as e:
            print(f"Error in manual cancel_all_orders for {symbol}: {e}")
            return False

    def place_limit_order(self, symbol, side, amount, price):
        try:
            order = self.exchange.create_order(symbol, 'limit', side, amount, price)
            print(f"Placed {side} limit order for {symbol} at {price}")
            return order
        except Exception as e:
            print(f"Error placing limit order for {symbol}: {e}")
            return None

    def place_stop_loss(self, symbol, side, amount, stop_price):
        try:
            # STOP_MARKET for Futures
            params = {'stopPrice': stop_price, 'reduceOnly': True}
            order = self.exchange.create_order(symbol, 'STOP_MARKET', side, amount, params=params)
            print(f"Placed Stop Loss for {symbol} at {stop_price}")
            return order
        except Exception as e:
            print(f"Error placing SL for {symbol}: {e}")
            return None

    def place_take_profit(self, symbol, side, amount, tp_price):
        try:
            # TAKE_PROFIT_MARKET for Futures
            params = {'stopPrice': tp_price, 'reduceOnly': True}
            order = self.exchange.create_order(symbol, 'TAKE_PROFIT_MARKET', side, amount, params=params)
            print(f"Placed Take Profit for {symbol} at {tp_price}")
            return order
        except Exception as e:
            print(f"Error placing TP for {symbol}: {e}")
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
                orders = self.exchange.fetch_open_orders(symbol)
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
            orders = self.get_open_orders(symbol)
            sl_order = None
            tp_order = None
            
            for order in orders:
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
        try:
            # Create a MARKET order with reduceOnly=True
            params = {'reduceOnly': True}
            order = self.exchange.create_order(symbol, 'market', side, amount, params=params)
            print(f"⚠️ FORCED CLOSURE ({reason}): Closed {amount} {symbol} position with market {side} order")
            return order
        except Exception as e:
            print(f"Error closing position for {symbol} with market order: {e}")
            return None
