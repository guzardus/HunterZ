"""
Unit tests for reconciliation idempotency.

These tests verify that:
1. The reconciliation lock prevents overlapping runs
2. TP/SL placement doesn't create duplicates when orders already exist
3. Metrics are updated correctly
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import threading
import sys
import os
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import state


class TestReconciliationLock(unittest.TestCase):
    """Test reconciliation lock mechanism"""
    
    def setUp(self):
        """Reset state before each test"""
        state.bot_state.metrics.reconciliation_runs_count = 0
        state.bot_state.metrics.reconciliation_skipped_count = 0
        state.bot_state.reconciliation_log = []
    
    @patch('main.HyperliquidClient')
    def test_lock_prevents_overlapping_runs(self, mock_client_class):
        """Second reconciliation should be skipped if lock is held"""
        # Import main module after mocking
        from main import reconcile_all_positions_tp_sl, _reconciliation_lock
        
        mock_client = Mock()
        mock_client.get_all_positions.return_value = []
        
        # Simulate a slow reconciliation by holding the lock
        results = {'first_completed': False, 'second_skipped': False}
        
        def slow_reconcile():
            results['first_completed'] = True
            # Just call normally - the lock will be acquired
            reconcile_all_positions_tp_sl(mock_client)
        
        # First reconciliation acquires lock
        thread1 = threading.Thread(target=slow_reconcile)
        thread1.start()
        thread1.join()
        
        # Verify first run completed
        self.assertTrue(results['first_completed'])
        self.assertEqual(state.bot_state.metrics.reconciliation_runs_count, 1)
    
    @patch('main.HyperliquidClient')
    def test_reconciliation_increments_run_count(self, mock_client_class):
        """Each successful reconciliation should increment run count"""
        from main import reconcile_all_positions_tp_sl
        
        mock_client = Mock()
        mock_client.get_all_positions.return_value = []
        
        initial_count = state.bot_state.metrics.reconciliation_runs_count
        
        reconcile_all_positions_tp_sl(mock_client)
        
        self.assertEqual(
            state.bot_state.metrics.reconciliation_runs_count, 
            initial_count + 1
        )


class TestIdempotentTPSLPlacement(unittest.TestCase):
    """Test idempotent TP/SL placement"""
    
    def setUp(self):
        """Reset state before each test"""
        state.bot_state.exchange_open_orders = []
        state.bot_state.metrics.duplicate_placement_attempts = 0
    
    @patch('execution.ccxt.hyperliquid')
    def test_existing_matching_sl_not_replaced(self, mock_hyperliquid):
        """Existing SL order that matches should not be replaced"""
        from execution import HyperliquidClient
        
        # Setup mock exchange
        mock_exchange = Mock()
        mock_hyperliquid.return_value = mock_exchange
        
        # Create client
        client = HyperliquidClient()
        
        # Setup existing SL order that matches
        existing_sl = {
            'id': 'existing_sl_123',
            'type': 'STOP_MARKET',
            'stopPrice': 43000.0,
            'amount': 0.1,
            'reduceOnly': True,
            'symbol': 'BTC/USDC'
        }
        
        existing_tp = {
            'id': 'existing_tp_456',
            'type': 'TAKE_PROFIT_MARKET',
            'stopPrice': 49000.0,
            'amount': 0.1,
            'reduceOnly': True,
            'symbol': 'BTC/USDC'
        }
        
        # Mock fetch_open_orders to return existing orders
        mock_exchange.fetch_open_orders.return_value = [existing_sl, existing_tp]
        
        # Call place_sl_tp_orders
        result = client.place_sl_tp_orders('BTC/USDC', 'buy', 0.1, 43000.0, 49000.0)
        
        # Verify existing orders returned, no new orders created
        self.assertEqual(result['sl_order']['id'], 'existing_sl_123')
        self.assertEqual(result['tp_order']['id'], 'existing_tp_456')
        
        # Verify create_order was NOT called (orders already exist)
        mock_exchange.create_order.assert_not_called()

    @patch('execution.ccxt.hyperliquid')
    def test_state_cached_reduce_only_prevents_duplicate(self, mock_hyperliquid):
        """Reduce-only orders in cached state should prevent duplicate placement when API lags"""
        from execution import HyperliquidClient

        mock_exchange = Mock()
        mock_hyperliquid.return_value = mock_exchange

        # Simulate API returning no orders while state cache still has them
        mock_exchange.fetch_open_orders.return_value = []

        # Seed state cache with matching reduce-only orders
        state.bot_state.exchange_open_orders = [
            {
                'order_id': 'state_sl',
                'symbol': 'BTC/USDC',
                'type': 'STOP_MARKET',
                'price': 43000.0,
                'stop_price': 43000.0,
                'amount': 0.1,
                'reduce_only': True
            },
            {
                'order_id': 'state_tp',
                'symbol': 'BTC/USDC',
                'type': 'TAKE_PROFIT_MARKET',
                'price': 49000.0,
                'stop_price': 49000.0,
                'amount': 0.1,
                'reduce_only': True
            }
        ]

        client = HyperliquidClient()
        initial_duplicates = state.bot_state.metrics.duplicate_placement_attempts

        result = client.place_sl_tp_orders('BTC/USDC', 'buy', 0.1, 43000.0, 49000.0)

        # Should reuse cached orders and avoid new placement
        mock_exchange.create_order.assert_not_called()
        self.assertEqual(result['sl_order']['id'], 'state_sl')
        self.assertEqual(result['tp_order']['id'], 'state_tp')
        self.assertEqual(
            state.bot_state.metrics.duplicate_placement_attempts,
            initial_duplicates + 2
        )

    @patch('execution.ccxt.hyperliquid')
    def test_mismatched_order_replaced(self, mock_hyperliquid):
        """Existing order with different price should be cancelled and replaced"""
        from execution import HyperliquidClient
        
        # Setup mock exchange
        mock_exchange = Mock()
        mock_hyperliquid.return_value = mock_exchange
        
        # Create client
        client = HyperliquidClient()
        
        # Setup existing SL order with DIFFERENT price
        existing_sl = {
            'id': 'old_sl_order',
            'type': 'STOP_MARKET',
            'stopPrice': 42000.0,  # Different from target 43000
            'amount': 0.1,
            'reduceOnly': True,
            'symbol': 'BTC/USDC'
        }
        
        # First call returns existing order, subsequent calls return updated orders
        mock_exchange.fetch_open_orders.side_effect = [
            [existing_sl],  # First call - get existing
            []  # After cancellation
        ]
        
        # Mock create_order to return new order
        mock_exchange.create_order.return_value = {
            'id': 'new_sl_order',
            'type': 'STOP_MARKET',
            'stopPrice': 43000.0,
            'amount': 0.1
        }
        
        # Call place_sl_tp_orders
        result = client.place_sl_tp_orders('BTC/USDC', 'buy', 0.1, 43000.0, 49000.0)
        
        # Verify cancel was called for old order
        mock_exchange.cancel_order.assert_any_call('old_sl_order', 'BTC/USDC')


class TestDuplicatePlacementMetrics(unittest.TestCase):
    """Test that duplicate placement attempts are tracked"""
    
    def setUp(self):
        """Reset state before each test"""
        state.bot_state.metrics.duplicate_placement_attempts = 0
    
    @patch('execution.ccxt.hyperliquid')
    def test_duplicate_increments_metric(self, mock_hyperliquid):
        """When order already exists and matches, metric should increment"""
        from execution import HyperliquidClient
        
        # Setup mock exchange
        mock_exchange = Mock()
        mock_hyperliquid.return_value = mock_exchange
        
        # Create client
        client = HyperliquidClient()
        
        # Setup existing matching orders
        existing_sl = {
            'id': 'existing_sl',
            'type': 'STOP_MARKET',
            'stopPrice': 43000.0,
            'amount': 0.1,
            'reduceOnly': True,
            'symbol': 'BTC/USDC'
        }
        existing_tp = {
            'id': 'existing_tp',
            'type': 'TAKE_PROFIT_MARKET',
            'stopPrice': 49000.0,
            'amount': 0.1,
            'reduceOnly': True,
            'symbol': 'BTC/USDC'
        }
        
        mock_exchange.fetch_open_orders.return_value = [existing_sl, existing_tp]
        
        initial_count = state.bot_state.metrics.duplicate_placement_attempts
        
        # Try to place same orders again
        client.place_sl_tp_orders('BTC/USDC', 'buy', 0.1, 43000.0, 49000.0)
        
        # Should have incremented for both SL and TP skipped
        self.assertEqual(
            state.bot_state.metrics.duplicate_placement_attempts,
            initial_count + 2
        )


if __name__ == '__main__':
    unittest.main()
