"""
Unit tests for TP/SL reconciliation logic
"""
import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import state
import order_utils
from main import reconcile_position_tp_sl


class TestTPSLReconciliationLogic(unittest.TestCase):
    """Test TP/SL reconciliation decision logic"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Reset bot state before each test
        state.bot_state.positions = {}
        state.bot_state.exchange_open_orders = []
        state.bot_state.pending_orders = {}
        state.bot_state.reconciliation_log = []
    
    def test_compute_position_tp_sl_with_both_orders(self):
        """Test computing TP/SL when both orders exist"""
        symbol = 'BTC/USDT'
        exchange_orders = [
            {
                'symbol': 'BTC/USDT',
                'type': 'STOP_MARKET',
                'reduceOnly': True,
                'stopPrice': 40000.0
            },
            {
                'symbol': 'BTC/USDT',
                'type': 'TAKE_PROFIT_MARKET',
                'reduceOnly': True,
                'stopPrice': 50000.0
            }
        ]
        
        result = state.compute_position_tp_sl(symbol, exchange_orders)
        
        self.assertEqual(result['stop_loss'], 40000.0)
        self.assertEqual(result['take_profit'], 50000.0)
    
    def test_compute_position_tp_sl_with_stop_limit(self):
        """Test computing TP/SL with STOP_LIMIT order type (Hyperliquid)"""
        symbol = 'BTC/USDT'
        exchange_orders = [
            {
                'symbol': 'BTC/USDT',
                'type': 'STOP_LIMIT',
                'reduceOnly': True,
                'stopPrice': 40000.0,
                'price': 39900.0
            }
        ]
        
        result = state.compute_position_tp_sl(symbol, exchange_orders)
        
        self.assertEqual(result['stop_loss'], 40000.0)
        self.assertIsNone(result['take_profit'])
    
    def test_compute_position_tp_sl_with_take_profit_limit(self):
        """Test computing TP/SL with TAKE_PROFIT_LIMIT order type (Hyperliquid)"""
        symbol = 'ETH/USDT'
        exchange_orders = [
            {
                'symbol': 'ETH/USDT',
                'type': 'TAKE_PROFIT_LIMIT',
                'reduceOnly': True,
                'stopPrice': 3200.0,
                'price': 3210.0
            }
        ]
        
        result = state.compute_position_tp_sl(symbol, exchange_orders)
        
        self.assertIsNone(result['stop_loss'])
        self.assertEqual(result['take_profit'], 3200.0)
    
    def test_compute_position_tp_sl_with_generic_stop_types(self):
        """Test computing TP/SL with generic STOP and TAKE_PROFIT types"""
        symbol = 'SOL/USDT'
        exchange_orders = [
            {
                'symbol': 'SOL/USDT',
                'type': 'STOP',
                'reduceOnly': True,
                'price': 120.0
            },
            {
                'symbol': 'SOL/USDT',
                'type': 'TAKE_PROFIT',
                'reduceOnly': True,
                'price': 140.0
            }
        ]
        
        result = state.compute_position_tp_sl(symbol, exchange_orders)
        
        self.assertEqual(result['stop_loss'], 120.0)
        self.assertEqual(result['take_profit'], 140.0)
    
    def test_compute_position_tp_sl_with_only_sl(self):
        """Test computing TP/SL when only SL exists"""
        symbol = 'ETH/USDT'
        exchange_orders = [
            {
                'symbol': 'ETH/USDT',
                'type': 'STOP_MARKET',
                'reduceOnly': True,
                'stopPrice': 2800.0
            }
        ]
        
        result = state.compute_position_tp_sl(symbol, exchange_orders)
        
        self.assertEqual(result['stop_loss'], 2800.0)
        self.assertIsNone(result['take_profit'])
    
    def test_compute_position_tp_sl_with_only_tp(self):
        """Test computing TP/SL when only TP exists"""
        symbol = 'SOL/USDT'
        exchange_orders = [
            {
                'symbol': 'SOL/USDT',
                'type': 'TAKE_PROFIT_MARKET',
                'reduceOnly': True,
                'stopPrice': 120.0
            }
        ]
        
        result = state.compute_position_tp_sl(symbol, exchange_orders)
        
        self.assertIsNone(result['stop_loss'])
        self.assertEqual(result['take_profit'], 120.0)
    
    def test_compute_position_tp_sl_no_orders(self):
        """Test computing TP/SL when no TP/SL orders exist"""
        symbol = 'BNB/USDT'
        exchange_orders = [
            {
                'symbol': 'BNB/USDT',
                'type': 'LIMIT',
                'reduceOnly': False
            }
        ]
        
        result = state.compute_position_tp_sl(symbol, exchange_orders)
        
        self.assertIsNone(result['stop_loss'])
        self.assertIsNone(result['take_profit'])
    
    def test_compute_position_tp_sl_different_symbol(self):
        """Test that TP/SL from different symbol is not used"""
        symbol = 'BTC/USDT'
        exchange_orders = [
            {
                'symbol': 'ETH/USDT',  # Different symbol
                'type': 'STOP_MARKET',
                'reduceOnly': True,
                'stopPrice': 2800.0
            }
        ]
        
        result = state.compute_position_tp_sl(symbol, exchange_orders)
        
        self.assertIsNone(result['stop_loss'])
        self.assertIsNone(result['take_profit'])
    
    def test_enrich_positions_with_tp_sl(self):
        """Test enriching positions with TP/SL from orders"""
        # Set up a position
        state.bot_state.positions['BTC/USDT'] = {
            'symbol': 'BTC/USDT',
            'side': 'LONG',
            'size': 0.1,
            'entry_price': 45000.0,
            'mark_price': 46000.0,
            'unrealized_pnl': 100.0,
            'leverage': 10,
            'take_profit': None,
            'stop_loss': None
        }
        
        # Set up exchange orders
        state.bot_state.exchange_open_orders = [
            {
                'symbol': 'BTC/USDT',
                'type': 'STOP_MARKET',
                'reduceOnly': True,
                'stopPrice': 43000.0
            },
            {
                'symbol': 'BTC/USDT',
                'type': 'TAKE_PROFIT_MARKET',
                'reduceOnly': True,
                'stopPrice': 49000.0
            }
        ]
        
        # Enrich positions
        state.enrich_positions_with_tp_sl()
        
        # Verify TP/SL were added
        position = state.bot_state.positions['BTC/USDT']
        self.assertEqual(position['stop_loss'], 43000.0)
        self.assertEqual(position['take_profit'], 49000.0)
    
    def test_enrich_positions_with_tp_sl_multiple_positions(self):
        """Test enriching multiple positions with their respective TP/SL"""
        # Set up multiple positions
        state.bot_state.positions['BTC/USDT'] = {
            'symbol': 'BTC/USDT',
            'side': 'LONG',
            'size': 0.1,
            'entry_price': 45000.0,
            'take_profit': None,
            'stop_loss': None
        }
        state.bot_state.positions['ETH/USDT'] = {
            'symbol': 'ETH/USDT',
            'side': 'SHORT',
            'size': 2.0,
            'entry_price': 3000.0,
            'take_profit': None,
            'stop_loss': None
        }
        
        # Set up exchange orders for both
        state.bot_state.exchange_open_orders = [
            {
                'symbol': 'BTC/USDT',
                'type': 'STOP_MARKET',
                'stopPrice': 43000.0
            },
            {
                'symbol': 'BTC/USDT',
                'type': 'TAKE_PROFIT_MARKET',
                'stopPrice': 49000.0
            },
            {
                'symbol': 'ETH/USDT',
                'type': 'STOP_MARKET',
                'stopPrice': 3100.0
            },
            {
                'symbol': 'ETH/USDT',
                'type': 'TAKE_PROFIT_MARKET',
                'stopPrice': 2800.0
            }
        ]
        
        # Enrich positions
        state.enrich_positions_with_tp_sl()
        
        # Verify both positions got correct TP/SL
        btc_position = state.bot_state.positions['BTC/USDT']
        self.assertEqual(btc_position['stop_loss'], 43000.0)
        self.assertEqual(btc_position['take_profit'], 49000.0)
        
        eth_position = state.bot_state.positions['ETH/USDT']
        self.assertEqual(eth_position['stop_loss'], 3100.0)
        self.assertEqual(eth_position['take_profit'], 2800.0)

    @patch("main.order_utils.safe_place_tp_sl")
    @patch("main.order_utils.check_backoff", return_value=(False, 0))
    @patch("main.order_utils.fetch_symbol_tick_size", return_value=0.01)
    def test_reconcile_uses_explicit_short_side(self, mock_tick, mock_backoff, mock_safe_place):
        """Ensure reconcile_position_tp_sl respects explicit SHORT side even with positive size"""
        mock_safe_place.return_value = True

        mock_client = Mock()
        mock_client.exchange = Mock()
        mock_client.exchange.price_to_precision = Mock(side_effect=lambda s, p: p)
        mock_client.exchange.amount_to_precision = Mock(side_effect=lambda s, a: a)
        mock_client.get_tp_sl_orders_for_position = Mock(return_value={"sl_orders": [], "tp_orders": []})
        mock_client.cancel_order = Mock(return_value=True)

        position = {
            "symbol": "SOL/USDT",
            "side": "SHORT",
            # Positive position size with explicit SHORT side mimics hedged-mode payloads
            "positionAmt": 112.0,
            "entryPrice": 124.28,
        }

        success = reconcile_position_tp_sl(mock_client, "SOL/USDT", position, pending_order=None)

        self.assertTrue(success)
        mock_safe_place.assert_called_once()
        _, _, is_long_arg, _, tp_price, sl_price = mock_safe_place.call_args[0]

        self.assertFalse(is_long_arg)
        self.assertLess(tp_price, position["entryPrice"])
        self.assertGreater(sl_price, position["entryPrice"])
    
    def test_order_matches_target_exact_match(self):
        """Test order matching with exact price and amount match"""
        order = {
            'id': 'order123',
            'stopPrice': 45000.0,
            'amount': 0.1,
            'type': 'STOP_MARKET'
        }
        
        result = order_utils.order_matches_target(
            order, 
            target_price=45000.0, 
            target_amount=0.1, 
            tick_size=0.01,
            amount_tolerance=0.01
        )
        
        self.assertTrue(result)
    
    def test_order_matches_target_within_tolerance(self):
        """Test order matching within acceptable tolerance"""
        order = {
            'id': 'order456',
            'stopPrice': 45000.5,
            'amount': 0.101,  # 1% difference
            'type': 'STOP_MARKET'
        }
        
        result = order_utils.order_matches_target(
            order, 
            target_price=45000.0, 
            target_amount=0.1, 
            tick_size=1.0,  # Large tick size covers the difference
            amount_tolerance=0.02  # 2% tolerance
        )
        
        self.assertTrue(result)
    
    def test_order_matches_target_price_mismatch(self):
        """Test order matching fails with price mismatch"""
        order = {
            'id': 'order789',
            'stopPrice': 46000.0,  # Too different
            'amount': 0.1,
            'type': 'STOP_MARKET'
        }
        
        result = order_utils.order_matches_target(
            order, 
            target_price=45000.0, 
            target_amount=0.1, 
            tick_size=0.01,
            amount_tolerance=0.01
        )
        
        self.assertFalse(result)
    
    def test_order_matches_target_amount_mismatch(self):
        """Test order matching fails with amount mismatch"""
        order = {
            'id': 'order999',
            'stopPrice': 45000.0,
            'amount': 0.2,  # 100% difference
            'type': 'STOP_MARKET'
        }
        
        result = order_utils.order_matches_target(
            order, 
            target_price=45000.0, 
            target_amount=0.1, 
            tick_size=0.01,
            amount_tolerance=0.01
        )
        
        self.assertFalse(result)
    
    def test_order_matches_target_with_price_field(self):
        """Test order matching uses price field when stopPrice is missing"""
        order = {
            'id': 'order_limit',
            'price': 45000.0,  # No stopPrice for limit orders
            'amount': 0.1,
            'type': 'STOP_LIMIT'
        }
        
        result = order_utils.order_matches_target(
            order, 
            target_price=45000.0, 
            target_amount=0.1, 
            tick_size=0.01,
            amount_tolerance=0.01
        )
        
        self.assertTrue(result)
    
    @patch("main.order_utils.safe_place_tp_sl")
    @patch("main.order_utils.check_backoff", return_value=(False, 0))
    @patch("main.order_utils.fetch_symbol_tick_size", return_value=0.01)
    @patch("main.order_utils.order_matches_target")
    def test_reconcile_deduplicates_multiple_sl_orders(self, mock_match, mock_tick, mock_backoff, mock_safe_place):
        """Test reconciliation deduplicates multiple SL orders"""
        # Match calls: First SL order in dedup (True - breaks loop), then single TP order (True)
        mock_match.side_effect = [True, True]  # Keep first SL, keep TP
        mock_safe_place.return_value = True  # Should not be called since orders match
        
        mock_client = Mock()
        mock_client.exchange = Mock()
        mock_client.exchange.price_to_precision = Mock(side_effect=lambda s, p: p)
        mock_client.exchange.amount_to_precision = Mock(side_effect=lambda s, a: a)
        
        # Multiple SL orders exist, single TP order exists
        mock_client.get_tp_sl_orders_for_position = Mock(return_value={
            "sl_orders": [
                {"id": "sl1", "stopPrice": 40000.0, "amount": 0.1, "type": "STOP_MARKET"},
                {"id": "sl2", "stopPrice": 40100.0, "amount": 0.1, "type": "STOP_MARKET"},
                {"id": "sl3", "stopPrice": 40200.0, "amount": 0.1, "type": "STOP_MARKET"}
            ],
            "tp_orders": [
                {"id": "tp1", "stopPrice": 50000.0, "amount": 0.1, "type": "TAKE_PROFIT_MARKET"}
            ]
        })
        mock_client.cancel_order = Mock(return_value=True)
        
        position = {
            "symbol": "BTC/USDT",
            "side": "LONG",
            "positionAmt": 0.1,
            "entryPrice": 45000.0,
        }
        
        success = reconcile_position_tp_sl(mock_client, "BTC/USDT", position, pending_order=None)
        
        # Should keep first matching SL order and matching TP order, cancel the other two SL orders only
        self.assertTrue(success)
        # Verify the number of order_matches_target calls (1 for first SL + 1 for TP)
        self.assertEqual(mock_match.call_count, 2, 
                        f"Expected 2 calls to order_matches_target but got {mock_match.call_count}")
        # Should cancel only the mismatched SL orders
        self.assertEqual(mock_client.cancel_order.call_count, 2, 
                        f"Expected 2 cancellations but got {mock_client.cancel_order.call_count}. "
                        f"Calls: {mock_client.cancel_order.call_args_list}")
        mock_client.cancel_order.assert_any_call("BTC/USDT", "sl2")
        mock_client.cancel_order.assert_any_call("BTC/USDT", "sl3")
        # Should not place new orders since we kept matching ones
        mock_safe_place.assert_not_called()
    
    @patch("main.order_utils.safe_place_tp_sl")
    @patch("main.order_utils.check_backoff", return_value=(False, 0))
    @patch("main.order_utils.fetch_symbol_tick_size", return_value=0.01)
    @patch("main.order_utils.order_matches_target")
    def test_reconcile_cancels_all_when_no_match(self, mock_match, mock_tick, mock_backoff, mock_safe_place):
        """Test reconciliation cancels all orders and replaces when none match"""
        mock_match.return_value = False  # None match
        mock_safe_place.return_value = True  # Successfully places new orders
        
        mock_client = Mock()
        mock_client.exchange = Mock()
        mock_client.exchange.price_to_precision = Mock(side_effect=lambda s, p: p)
        mock_client.exchange.amount_to_precision = Mock(side_effect=lambda s, a: a)
        
        # Multiple orders exist but none match
        mock_client.get_tp_sl_orders_for_position = Mock(return_value={
            "sl_orders": [
                {"id": "sl1", "stopPrice": 40000.0, "amount": 0.2, "type": "STOP_MARKET"},
                {"id": "sl2", "stopPrice": 40100.0, "amount": 0.2, "type": "STOP_MARKET"}
            ],
            "tp_orders": [
                {"id": "tp1", "stopPrice": 50000.0, "amount": 0.2, "type": "TAKE_PROFIT_MARKET"}
            ]
        })
        mock_client.cancel_order = Mock(return_value=True)
        
        position = {
            "symbol": "ETH/USDT",
            "side": "LONG",
            "positionAmt": 0.1,
            "entryPrice": 3000.0,
        }
        
        success = reconcile_position_tp_sl(mock_client, "ETH/USDT", position, pending_order=None)
        
        # Should cancel all mismatched orders
        self.assertEqual(mock_client.cancel_order.call_count, 3)
        # Should place new orders
        mock_safe_place.assert_called_once()
        self.assertTrue(success)


if __name__ == '__main__':
    unittest.main()
