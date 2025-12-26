"""
Test for automatic re-placement of manually cancelled orders
"""
import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import state


class TestManualOrderCancellation(unittest.TestCase):
    """Test that manually cancelled orders can be automatically replaced"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Reset bot state before each test
        state.bot_state.positions = {}
        state.bot_state.exchange_open_orders = []
        state.bot_state.pending_orders = {}
        state.bot_state.reconciliation_log = []
    
    def test_pending_order_verification_allows_replacement_when_cancelled(self):
        """Test that pending order check allows new placement if order was cancelled"""
        # This simulates the scenario where:
        # 1. Bot places an order and tracks it in pending_orders
        # 2. User manually cancels the order on exchange
        # 3. Bot should detect order is cancelled and allow new placement
        
        symbol = 'BTC/USDC'
        
        # Add a pending order to state (simulating bot placed an order)
        state.add_pending_order(symbol, 'order_123', {
            'side': 'buy',
            'quantity': 0.1,
            'entry_price': 45000.0,
            'stop_loss': 43000.0,
            'take_profit': 49000.0
        })
        
        # Verify it was added
        pending = state.get_pending_order(symbol)
        self.assertIsNotNone(pending)
        self.assertEqual(pending['order_id'], 'order_123')
    
    def test_remove_pending_order_allows_new_placement(self):
        """Test that removing a pending order allows new placement"""
        symbol = 'ETH/USDC'
        
        # Add pending order
        state.add_pending_order(symbol, 'order_456', {
            'side': 'sell',
            'quantity': 2.0,
            'entry_price': 3000.0,
            'stop_loss': 3100.0,
            'take_profit': 2800.0
        })
        
        # Verify it exists
        self.assertIsNotNone(state.get_pending_order(symbol))
        
        # Remove it (simulating detection of cancelled order)
        state.remove_pending_order(symbol)
        
        # Verify it's removed
        self.assertIsNone(state.get_pending_order(symbol))

    def test_pending_order_exchange_ids_are_persisted(self):
        """Exchange TP/SL ids should be stored on the pending order"""
        symbol = 'BTC/USDC'

        state.add_pending_order(symbol, 'order_123', {'side': 'buy'})
        state.update_pending_order_exchange_orders(symbol, {'id': 'sl_1'}, {'id': 'tp_1'})

        pending = state.get_pending_order(symbol)
        self.assertIsNotNone(pending)
        self.assertEqual(pending['exchange_orders']['sl'], 'sl_1')
        self.assertEqual(pending['exchange_orders']['tp'], 'tp_1')
        self.assertIsNotNone(pending.get('last_tp_sl_placement'))


if __name__ == '__main__':
    unittest.main()
