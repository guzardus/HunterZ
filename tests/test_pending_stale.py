"""
Unit tests for stale pending order handling.

These tests verify that:
1. Pending orders have created_at timestamps
2. Stale pending orders are detected correctly
3. Stale orders are cancelled and removed
"""
import unittest
from unittest.mock import Mock, patch
import datetime
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import state


class TestStalePendingOrderDetection(unittest.TestCase):
    """Test stale pending order detection"""
    
    def setUp(self):
        """Reset state before each test"""
        state.bot_state.pending_orders = {}
        state.bot_state.metrics.pending_order_stale_count = 0
    
    def test_new_order_has_created_at(self):
        """New pending orders should have created_at timestamp"""
        state.add_pending_order('BTC/USDC', 'order123', {'side': 'buy'})
        
        pending = state.get_pending_order('BTC/USDC')
        self.assertIn('created_at', pending)
        self.assertIsNotNone(pending['created_at'])
    
    def test_no_stale_orders_when_fresh(self):
        """Fresh orders should not be detected as stale"""
        state.add_pending_order('BTC/USDC', 'order123', {'side': 'buy'})
        
        # With 1 hour threshold, fresh order should not be stale
        stale = state.get_stale_pending_orders(3600)
        
        self.assertEqual(len(stale), 0)
    
    def test_old_order_detected_as_stale(self):
        """Orders older than threshold should be detected as stale"""
        # Add order with old timestamp
        old_time = datetime.datetime.now() - datetime.timedelta(hours=2)
        state.bot_state.pending_orders['BTC/USDC'] = {
            'order_id': 'old_order',
            'params': {'side': 'buy'},
            'timestamp': old_time.isoformat(),
            'created_at': old_time.isoformat()
        }
        
        # With 1 hour threshold, 2 hour old order should be stale
        stale = state.get_stale_pending_orders(3600)
        
        self.assertEqual(len(stale), 1)
        self.assertIn('BTC/USDC', stale)
        self.assertIn('age_seconds', stale['BTC/USDC'])
        self.assertGreater(stale['BTC/USDC']['age_seconds'], 3600)
    
    def test_mixed_fresh_and_stale(self):
        """Should only return stale orders, not fresh ones"""
        # Add stale order
        old_time = datetime.datetime.now() - datetime.timedelta(hours=2)
        state.bot_state.pending_orders['OLD/USDC'] = {
            'order_id': 'old_order',
            'params': {'side': 'buy'},
            'timestamp': old_time.isoformat(),
            'created_at': old_time.isoformat()
        }
        
        # Add fresh order
        state.add_pending_order('FRESH/USDC', 'fresh_order', {'side': 'sell'})
        
        # With 1 hour threshold
        stale = state.get_stale_pending_orders(3600)
        
        self.assertEqual(len(stale), 1)
        self.assertIn('OLD/USDC', stale)
        self.assertNotIn('FRESH/USDC', stale)
    
    def test_handles_missing_created_at(self):
        """Should handle orders without created_at by using timestamp"""
        old_time = datetime.datetime.now() - datetime.timedelta(hours=2)
        state.bot_state.pending_orders['BTC/USDC'] = {
            'order_id': 'old_order',
            'params': {'side': 'buy'},
            'timestamp': old_time.isoformat()
            # No created_at - should fall back to timestamp
        }
        
        stale = state.get_stale_pending_orders(3600)
        
        self.assertEqual(len(stale), 1)
    
    def test_handles_invalid_timestamp(self):
        """Should skip orders with invalid timestamps"""
        state.bot_state.pending_orders['BTC/USDC'] = {
            'order_id': 'bad_order',
            'params': {'side': 'buy'},
            'timestamp': 'invalid_date',
            'created_at': 'not_a_date'
        }
        
        # Should not raise, just return empty
        stale = state.get_stale_pending_orders(3600)
        
        self.assertEqual(len(stale), 0)


class TestStalePendingOrderHandling(unittest.TestCase):
    """Test stale pending order handling in main loop"""
    
    def setUp(self):
        """Reset state before each test"""
        state.bot_state.pending_orders = {}
        state.bot_state.metrics.pending_order_stale_count = 0
        state.bot_state.metrics.cancelled_orders_count = 0
        state.bot_state.reconciliation_log = []
    
    @patch('main.HyperliquidClient')
    def test_stale_order_cancelled(self, mock_client_class):
        """Stale orders should be cancelled"""
        from main import handle_stale_pending_orders
        import config
        
        mock_client = Mock()
        mock_client.cancel_order.return_value = True
        
        # Add stale order
        old_time = datetime.datetime.now() - datetime.timedelta(seconds=config.PENDING_ORDER_STALE_SECONDS + 100)
        state.bot_state.pending_orders['BTC/USDC'] = {
            'order_id': 'stale_order',
            'params': {'side': 'buy'},
            'created_at': old_time.isoformat()
        }
        
        handle_stale_pending_orders(mock_client)
        
        # Verify cancel was called
        mock_client.cancel_order.assert_called_with('BTC/USDC', 'stale_order')
        
        # Verify order removed from pending
        self.assertNotIn('BTC/USDC', state.bot_state.pending_orders)
        
        # Verify metric incremented
        self.assertEqual(state.bot_state.metrics.pending_order_stale_count, 1)
    
    @patch('main.HyperliquidClient')
    def test_stale_order_removed_even_if_cancel_fails(self, mock_client_class):
        """Stale orders should be removed even if cancel fails"""
        from main import handle_stale_pending_orders
        import config
        
        mock_client = Mock()
        mock_client.cancel_order.return_value = False  # Cancel fails
        
        # Add stale order
        old_time = datetime.datetime.now() - datetime.timedelta(seconds=config.PENDING_ORDER_STALE_SECONDS + 100)
        state.bot_state.pending_orders['BTC/USDC'] = {
            'order_id': 'stale_order',
            'params': {'side': 'buy'},
            'created_at': old_time.isoformat()
        }
        
        handle_stale_pending_orders(mock_client)
        
        # Order should still be removed from pending
        self.assertNotIn('BTC/USDC', state.bot_state.pending_orders)
    
    @patch('main.HyperliquidClient')
    def test_reconciliation_log_entry_created(self, mock_client_class):
        """Stale order handling should create reconciliation log entry"""
        from main import handle_stale_pending_orders
        import config
        
        mock_client = Mock()
        mock_client.cancel_order.return_value = True
        
        # Add stale order
        old_time = datetime.datetime.now() - datetime.timedelta(seconds=config.PENDING_ORDER_STALE_SECONDS + 100)
        state.bot_state.pending_orders['BTC/USDC'] = {
            'order_id': 'stale_order',
            'params': {'side': 'buy'},
            'created_at': old_time.isoformat()
        }
        
        handle_stale_pending_orders(mock_client)
        
        # Check log entry was created
        self.assertGreater(len(state.bot_state.reconciliation_log), 0)
        log_entry = state.bot_state.reconciliation_log[0]
        self.assertIn('stale', log_entry.get('action', ''))


if __name__ == '__main__':
    unittest.main()
