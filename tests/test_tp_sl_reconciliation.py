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
    def test_reconcile_uses_explicit_short_side(self, mock_backoff, mock_safe_place):
        """Ensure reconcile_position_tp_sl respects explicit SHORT side even with positive size"""
        mock_safe_place.return_value = True

        mock_client = Mock()
        mock_client.exchange = Mock()
        mock_client.exchange.price_to_precision = Mock(side_effect=lambda s, p: p)
        mock_client.exchange.amount_to_precision = Mock(side_effect=lambda s, a: a)
        mock_client.get_tp_sl_orders_for_position = Mock(return_value={"sl_order": None, "tp_order": None})
        mock_client.cancel_order = Mock(return_value=True)

        position = {
            "symbol": "SOL/USDT",
            "side": "SHORT",
            "positionAmt": 112.0,
            "entryPrice": 124.28,
        }

        success = reconcile_position_tp_sl(mock_client, "SOL/USDT", position, pending_order=None)

        self.assertTrue(success)
        mock_safe_place.assert_called_once()
        called_args = mock_safe_place.call_args[0]
        is_long_arg = called_args[2]
        tp_price = called_args[4]
        sl_price = called_args[5]

        self.assertFalse(is_long_arg)
        self.assertLess(tp_price, position["entryPrice"])
        self.assertGreater(sl_price, position["entryPrice"])


if __name__ == '__main__':
    unittest.main()
