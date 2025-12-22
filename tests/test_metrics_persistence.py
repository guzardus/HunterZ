"""
Test metrics persistence functionality.
"""
import unittest
import sys
import os
import tempfile
import json

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import state

class TestMetricsPersistence(unittest.TestCase):
    """Test that metrics are properly persisted and loaded."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Use temporary files for testing
        self.temp_dir = tempfile.mkdtemp()
        state.METRICS_FILE = os.path.join(self.temp_dir, 'metrics.json')
        state.TRADE_HISTORY_FILE = os.path.join(self.temp_dir, 'trade_history.json')
        
        # Reset state
        state.bot_state.metrics.pending_orders_count = 0
        state.bot_state.metrics.open_exchange_orders_count = 0
        state.bot_state.metrics.placed_orders_count = 0
        state.bot_state.metrics.cancelled_orders_count = 0
        state.bot_state.metrics.filled_orders_count = 0
        state.bot_state.trade_history = []
        state.bot_state.total_pnl = 0.0
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Remove temporary files
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_save_and_load_metrics(self):
        """Test that metrics can be saved and loaded."""
        # Set some metrics
        state.bot_state.metrics.placed_orders_count = 10
        state.bot_state.metrics.cancelled_orders_count = 2
        state.bot_state.metrics.filled_orders_count = 8
        
        # Save metrics
        state.save_metrics()
        
        # Verify file was created
        self.assertTrue(os.path.exists(state.METRICS_FILE))
        
        # Reset metrics
        state.bot_state.metrics.placed_orders_count = 0
        state.bot_state.metrics.cancelled_orders_count = 0
        state.bot_state.metrics.filled_orders_count = 0
        
        # Load metrics
        state.load_metrics_on_startup()
        
        # Verify metrics were restored
        self.assertEqual(state.bot_state.metrics.placed_orders_count, 10)
        self.assertEqual(state.bot_state.metrics.cancelled_orders_count, 2)
        self.assertEqual(state.bot_state.metrics.filled_orders_count, 8)
    
    def test_save_and_load_trade_history(self):
        """Test that trade history can be saved and loaded."""
        # Add some trades
        trade1 = {
            'symbol': 'BTC/USDC',
            'side': 'LONG',
            'entry_price': 45000,
            'exit_price': 46000,
            'size': 0.1,
            'pnl': 100,
            'status': 'CLOSED',
            'timestamp': '2024-01-01T00:00:00'
        }
        trade2 = {
            'symbol': 'ETH/USDC',
            'side': 'SHORT',
            'entry_price': 3000,
            'exit_price': 2900,
            'size': 1.0,
            'pnl': 100,
            'status': 'CLOSED',
            'timestamp': '2024-01-02T00:00:00'
        }
        
        state.add_trade(trade1)
        state.add_trade(trade2)
        
        # Verify file was created (add_trade calls save_trade_history)
        self.assertTrue(os.path.exists(state.TRADE_HISTORY_FILE))
        
        # Reset trade history
        state.bot_state.trade_history = []
        state.bot_state.total_pnl = 0.0
        
        # Load trade history
        state.load_trade_history_on_startup()
        
        # Verify trades were restored
        self.assertEqual(len(state.bot_state.trade_history), 2)
        self.assertEqual(state.bot_state.total_pnl, 200.0)
    
    def test_calculate_pnl_from_trade_history(self):
        """Test that total P&L is correctly calculated from trade history."""
        # Add trades with different P&L
        trades = [
            {'symbol': 'BTC/USDC', 'pnl': 100, 'status': 'CLOSED'},
            {'symbol': 'ETH/USDC', 'pnl': -50, 'status': 'CLOSED'},
            {'symbol': 'SOL/USDC', 'pnl': 75, 'status': 'CLOSED'},
            {'symbol': 'UNI/USDC', 'pnl': None, 'status': 'OPEN'},  # Should be ignored
        ]
        
        for trade in trades:
            state.add_trade(trade)
        
        # Reset and reload
        state.bot_state.total_pnl = 0.0
        state.load_trade_history_on_startup()
        
        # Verify total P&L (100 - 50 + 75 = 125)
        self.assertEqual(state.bot_state.total_pnl, 125.0)
    
    def test_load_metrics_with_missing_file(self):
        """Test that loading metrics with missing file doesn't crash."""
        # Ensure file doesn't exist
        if os.path.exists(state.METRICS_FILE):
            os.remove(state.METRICS_FILE)
        
        # Should not raise exception
        state.load_metrics_on_startup()
        
        # Metrics should be at default values
        self.assertEqual(state.bot_state.metrics.placed_orders_count, 0)
    
    def test_load_trade_history_with_missing_file(self):
        """Test that loading trade history with missing file doesn't crash."""
        # Ensure file doesn't exist
        if os.path.exists(state.TRADE_HISTORY_FILE):
            os.remove(state.TRADE_HISTORY_FILE)
        
        # Should not raise exception
        state.load_trade_history_on_startup()
        
        # Trade history should be empty
        self.assertEqual(len(state.bot_state.trade_history), 0)
        self.assertEqual(state.bot_state.total_pnl, 0.0)

if __name__ == '__main__':
    unittest.main()
