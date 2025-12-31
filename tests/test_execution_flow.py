"""
Integration tests for TP/SL execution flow with mocked ccxt exchange
"""
import unittest
from unittest.mock import Mock, MagicMock, patch, call
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution import BinanceClient
import state


class TestTPSLExecutionFlow(unittest.TestCase):
    """Test TP/SL order placement flow with mocked exchange"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Reset bot state before each test
        state.bot_state.positions = {}
        state.bot_state.exchange_open_orders = []
        state.bot_state.pending_orders = {}
        state.bot_state.reconciliation_log = []
    
    @patch('execution.ccxt.binance')
    def test_place_sl_tp_orders_for_long_position(self, mock_binance_class):
        """Test placing TP/SL orders for a LONG position"""
        # Set up mock exchange
        mock_exchange = MagicMock()
        mock_binance_class.return_value = mock_exchange
        
        # Mock create_order to return order objects
        mock_exchange.create_order.side_effect = [
            {'id': 'sl_order_123', 'type': 'STOP_MARKET', 'status': 'open'},
            {'id': 'tp_order_456', 'type': 'TAKE_PROFIT_MARKET', 'status': 'open'}
        ]
        
        # Create client
        client = BinanceClient()
        
        # Place TP/SL orders for a LONG position
        result = client.place_sl_tp_orders(
            symbol='BTC/USDT',
            side='buy',  # Entry side (LONG)
            amount=0.1,
            sl_price=43000.0,
            tp_price=49000.0
        )
        
        # Verify both orders were created
        self.assertIsNotNone(result['sl_order'])
        self.assertIsNotNone(result['tp_order'])
        self.assertEqual(result['sl_order']['id'], 'sl_order_123')
        self.assertEqual(result['tp_order']['id'], 'tp_order_456')
        
        # Verify create_order was called twice with correct parameters
        self.assertEqual(mock_exchange.create_order.call_count, 2)
        
        # Check SL order call (close side is 'sell' for LONG)
        sl_call = mock_exchange.create_order.call_args_list[0]
        self.assertEqual(sl_call[0][0], 'BTC/USDT')
        self.assertEqual(sl_call[0][1], 'STOP_MARKET')
        self.assertEqual(sl_call[0][2], 'sell')
        self.assertEqual(sl_call[0][3], 0.1)
        self.assertEqual(sl_call[1]['params']['stopPrice'], 43000.0)
        self.assertTrue(sl_call[1]['params']['reduceOnly'])
        
        # Check TP order call
        tp_call = mock_exchange.create_order.call_args_list[1]
        self.assertEqual(tp_call[0][0], 'BTC/USDT')
        self.assertEqual(tp_call[0][1], 'TAKE_PROFIT_MARKET')
        self.assertEqual(tp_call[0][2], 'sell')
        self.assertEqual(tp_call[0][3], 0.1)
        self.assertEqual(tp_call[1]['params']['stopPrice'], 49000.0)
        self.assertTrue(tp_call[1]['params']['reduceOnly'])
    
    @patch('execution.ccxt.binance')
    def test_place_sl_tp_orders_for_short_position(self, mock_binance_class):
        """Test placing TP/SL orders for a SHORT position"""
        # Set up mock exchange
        mock_exchange = MagicMock()
        mock_binance_class.return_value = mock_exchange
        
        # Mock create_order to return order objects
        mock_exchange.create_order.side_effect = [
            {'id': 'sl_order_789', 'type': 'STOP_MARKET', 'status': 'open'},
            {'id': 'tp_order_012', 'type': 'TAKE_PROFIT_MARKET', 'status': 'open'}
        ]
        
        # Create client
        client = BinanceClient()
        
        # Place TP/SL orders for a SHORT position
        result = client.place_sl_tp_orders(
            symbol='ETH/USDT',
            side='sell',  # Entry side (SHORT)
            amount=2.0,
            sl_price=3100.0,
            tp_price=2800.0
        )
        
        # Verify both orders were created
        self.assertIsNotNone(result['sl_order'])
        self.assertIsNotNone(result['tp_order'])
        
        # Verify create_order was called with 'buy' side (close side for SHORT)
        sl_call = mock_exchange.create_order.call_args_list[0]
        self.assertEqual(sl_call[0][2], 'buy')  # Close side
        
        tp_call = mock_exchange.create_order.call_args_list[1]
        self.assertEqual(tp_call[0][2], 'buy')  # Close side
    
    @patch('execution.ccxt.binance')
    def test_get_tp_sl_orders_for_position(self, mock_binance_class):
        """Test retrieving TP/SL orders for a position"""
        # Set up mock exchange
        mock_exchange = MagicMock()
        mock_binance_class.return_value = mock_exchange
        
        # Mock fetch_open_orders to return TP/SL orders
        mock_exchange.fetch_open_orders.return_value = [
            {
                'id': 'limit_order_1',
                'symbol': 'BTC/USDT',
                'type': 'LIMIT',
                'reduceOnly': False
            },
            {
                'id': 'sl_order_1',
                'symbol': 'BTC/USDT',
                'type': 'STOP_MARKET',
                'reduceOnly': True,
                'stopPrice': 43000.0,
                'amount': 0.1
            },
            {
                'id': 'tp_order_1',
                'symbol': 'BTC/USDT',
                'type': 'TAKE_PROFIT_MARKET',
                'reduceOnly': True,
                'stopPrice': 49000.0,
                'amount': 0.1
            }
        ]
        
        # Create client
        client = BinanceClient()
        
        # Get TP/SL orders
        result = client.get_tp_sl_orders_for_position('BTC/USDT')
        
        # Verify correct orders were identified (now returns lists)
        self.assertEqual(len(result['sl_orders']), 1)
        self.assertEqual(len(result['tp_orders']), 1)
        self.assertEqual(result['sl_orders'][0]['id'], 'sl_order_1')
        self.assertEqual(result['tp_orders'][0]['id'], 'tp_order_1')
        self.assertEqual(result['sl_orders'][0]['stopPrice'], 43000.0)
        self.assertEqual(result['tp_orders'][0]['stopPrice'], 49000.0)
    
    @patch('execution.ccxt.binance')
    def test_get_tp_sl_orders_missing_sl(self, mock_binance_class):
        """Test retrieving TP/SL when SL is missing"""
        # Set up mock exchange
        mock_exchange = MagicMock()
        mock_binance_class.return_value = mock_exchange
        
        # Mock fetch_open_orders to return only TP order
        mock_exchange.fetch_open_orders.return_value = [
            {
                'id': 'tp_order_1',
                'symbol': 'BTC/USDT',
                'type': 'TAKE_PROFIT_MARKET',
                'reduceOnly': True,
                'stopPrice': 49000.0
            }
        ]
        
        # Create client
        client = BinanceClient()
        
        # Get TP/SL orders
        result = client.get_tp_sl_orders_for_position('BTC/USDT')
        
        # Verify SL is empty list and TP has one order (now returns lists)
        self.assertEqual(len(result['sl_orders']), 0)
        self.assertEqual(len(result['tp_orders']), 1)
        self.assertEqual(result['tp_orders'][0]['id'], 'tp_order_1')
    
    @patch('execution.ccxt.binance')
    def test_get_tp_sl_orders_missing_tp(self, mock_binance_class):
        """Test retrieving TP/SL when TP is missing"""
        # Set up mock exchange
        mock_exchange = MagicMock()
        mock_binance_class.return_value = mock_exchange
        
        # Mock fetch_open_orders to return only SL order
        mock_exchange.fetch_open_orders.return_value = [
            {
                'id': 'sl_order_1',
                'symbol': 'BTC/USDT',
                'type': 'STOP_MARKET',
                'reduceOnly': True,
                'stopPrice': 43000.0
            }
        ]
        
        # Create client
        client = BinanceClient()
        
        # Get TP/SL orders
        result = client.get_tp_sl_orders_for_position('BTC/USDT')
        
        # Verify TP is empty list and SL has one order (now returns lists)
        self.assertEqual(len(result['sl_orders']), 1)
        self.assertEqual(len(result['tp_orders']), 0)
        self.assertEqual(result['sl_orders'][0]['id'], 'sl_order_1')
    
    @patch('execution.ccxt.binance')
    def test_cancel_and_replace_tp_sl_on_quantity_mismatch(self, mock_binance_class):
        """Test cancelling and replacing TP/SL when quantities don't match"""
        # Set up mock exchange
        mock_exchange = MagicMock()
        mock_binance_class.return_value = mock_exchange
        
        # Mock cancel_order
        mock_exchange.cancel_order.return_value = {'status': 'canceled'}
        
        # Mock create_order for new orders
        mock_exchange.create_order.side_effect = [
            {'id': 'new_sl_order', 'type': 'STOP_MARKET'},
            {'id': 'new_tp_order', 'type': 'TAKE_PROFIT_MARKET'}
        ]
        
        # Create client
        client = BinanceClient()
        
        # Cancel old order
        cancel_result = client.cancel_order('BTC/USDT', 'old_sl_order')
        self.assertTrue(cancel_result)
        
        # Place new TP/SL orders
        new_orders = client.place_sl_tp_orders(
            symbol='BTC/USDT',
            side='buy',
            amount=0.2,  # New quantity
            sl_price=43000.0,
            tp_price=49000.0
        )
        
        # Verify old order was cancelled and new orders were placed
        mock_exchange.cancel_order.assert_called_once_with('old_sl_order', 'BTC/USDT')
        self.assertEqual(mock_exchange.create_order.call_count, 2)
        self.assertEqual(new_orders['sl_order']['id'], 'new_sl_order')
        self.assertEqual(new_orders['tp_order']['id'], 'new_tp_order')


if __name__ == '__main__':
    unittest.main()
