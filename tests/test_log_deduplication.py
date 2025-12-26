"""
Unit tests for log deduplication functionality.

These tests verify that repeated log messages are suppressed to reduce noise,
while still logging when state changes occur.
"""
import unittest
from unittest.mock import patch
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import state


class TestPendingOrderLogDeduplication(unittest.TestCase):
    """Test deduplication of 'pending order still active' logs"""
    
    def setUp(self):
        """Reset state before each test"""
        state.bot_state.pending_orders = {}
        state.bot_state._logged_pending_order_ids = {}
        state.bot_state.reconciliation_log = []
    
    def test_should_log_first_detection(self):
        """First detection of a pending order should be logged"""
        symbol = 'BTC/USDC:USDC'
        order_id = '12345'
        
        result = state.should_log_pending_order_still_active(symbol, order_id)
        
        self.assertTrue(result)
    
    def test_should_not_log_repeated_detection(self):
        """Repeated detection of same order should not be logged"""
        symbol = 'BTC/USDC:USDC'
        order_id = '12345'
        
        # First detection
        state.should_log_pending_order_still_active(symbol, order_id)
        
        # Second detection of same order
        result = state.should_log_pending_order_still_active(symbol, order_id)
        
        self.assertFalse(result)
    
    def test_should_log_new_order_for_same_symbol(self):
        """New order for same symbol should be logged"""
        symbol = 'BTC/USDC:USDC'
        old_order_id = '12345'
        new_order_id = '67890'
        
        # First order
        state.should_log_pending_order_still_active(symbol, old_order_id)
        
        # New order for same symbol
        result = state.should_log_pending_order_still_active(symbol, new_order_id)
        
        self.assertTrue(result)
    
    def test_different_symbols_logged_independently(self):
        """Different symbols should be tracked independently"""
        symbol1 = 'BTC/USDC:USDC'
        symbol2 = 'ETH/USDC:USDC'
        order_id = '12345'
        
        # Log for symbol1
        result1 = state.should_log_pending_order_still_active(symbol1, order_id)
        # Log for symbol2 (same order id, different symbol)
        result2 = state.should_log_pending_order_still_active(symbol2, order_id)
        
        self.assertTrue(result1)
        self.assertTrue(result2)
    
    def test_clear_tracking_on_remove_pending_order(self):
        """Removing a pending order should clear log tracking"""
        symbol = 'BTC/USDC:USDC'
        order_id = '12345'
        
        # Add and track a pending order
        state.add_pending_order(symbol, order_id, {'side': 'buy'})
        state.should_log_pending_order_still_active(symbol, order_id)
        
        # Verify it's tracked
        self.assertFalse(state.should_log_pending_order_still_active(symbol, order_id))
        
        # Remove the pending order
        state.remove_pending_order(symbol)
        
        # New order should be logged again
        result = state.should_log_pending_order_still_active(symbol, order_id)
        self.assertTrue(result)
    
    def test_clear_pending_order_log_tracking_directly(self):
        """Test direct clearing of log tracking"""
        symbol = 'BTC/USDC:USDC'
        order_id = '12345'
        
        # Track order
        state.should_log_pending_order_still_active(symbol, order_id)
        
        # Clear tracking directly
        state.clear_pending_order_log_tracking(symbol)
        
        # Same order should be logged again
        result = state.should_log_pending_order_still_active(symbol, order_id)
        self.assertTrue(result)
    
    def test_clear_nonexistent_symbol_is_safe(self):
        """Clearing tracking for non-existent symbol should not raise"""
        # Should not raise any exception
        state.clear_pending_order_log_tracking('NONEXISTENT/USDC:USDC')


class TestExitPriceFallbackWarningDeduplication(unittest.TestCase):
    """Test deduplication of exit_price fallback warnings"""
    
    def setUp(self):
        """Reset state before each test"""
        state.bot_state._exit_price_fallback_warned = set()
        state.bot_state.trade_history = []
    
    def test_should_warn_first_time(self):
        """First fallback for a symbol should warn"""
        symbol = 'SOL/USDC:USDC'
        
        result = state.should_warn_exit_price_fallback(symbol)
        
        self.assertTrue(result)
    
    def test_should_not_warn_second_time(self):
        """Second fallback for same symbol should not warn"""
        symbol = 'SOL/USDC:USDC'
        
        # First warning
        state.should_warn_exit_price_fallback(symbol)
        
        # Second time
        result = state.should_warn_exit_price_fallback(symbol)
        
        self.assertFalse(result)
    
    def test_different_symbols_warned_independently(self):
        """Different symbols should be warned independently"""
        symbol1 = 'SOL/USDC:USDC'
        symbol2 = 'BTC/USDC:USDC'
        
        result1 = state.should_warn_exit_price_fallback(symbol1)
        result2 = state.should_warn_exit_price_fallback(symbol2)
        
        self.assertTrue(result1)
        self.assertTrue(result2)
    
    def test_clear_warning_allows_new_warning(self):
        """Clearing warning should allow it again"""
        symbol = 'SOL/USDC:USDC'
        
        # First warning
        state.should_warn_exit_price_fallback(symbol)
        
        # Clear
        state.clear_exit_price_fallback_warning(symbol)
        
        # Should warn again
        result = state.should_warn_exit_price_fallback(symbol)
        self.assertTrue(result)
    
    def test_clear_nonexistent_symbol_is_safe(self):
        """Clearing warning for non-existent symbol should not raise"""
        # Should not raise any exception
        state.clear_exit_price_fallback_warning('NONEXISTENT/USDC:USDC')


class TestCloseTradeInHistoryWithWarningDeduplication(unittest.TestCase):
    """Test that _close_trade_in_history respects warning deduplication"""
    
    def setUp(self):
        """Reset state before each test"""
        state.bot_state.trade_history = []
        state.bot_state.total_pnl = 0.0
        state.bot_state._exit_price_fallback_warned = set()
    
    def test_exit_price_fallback_warning_only_once(self):
        """Warning should only appear once even if _close_trade_in_history called multiple times"""
        symbol = 'SOL/USDC:USDC'
        
        # Add two trades that would need exit_price fallback
        state.add_trade({
            'symbol': symbol,
            'side': 'LONG',
            'entry_price': 100.0,
            'exit_price': None,
            'size': 1.0,
            'pnl': None,
            'status': 'OPEN'
        })
        
        # Position with no mark_price (triggers fallback)
        old_position = {
            'mark_price': 0,
            'entry_price': 105.0,
            'size': 1.0,
            'side': 'LONG'
        }
        
        # Capture print output
        with patch('builtins.print') as mock_print:
            state._close_trade_in_history(symbol, old_position)
            
            # Find how many times the warning was printed
            warning_calls = [
                call for call in mock_print.call_args_list 
                if 'Using entry_price as exit_price fallback' in str(call)
            ]
            self.assertEqual(len(warning_calls), 1)
    
    def test_warning_cleared_after_trade_close(self):
        """Warning tracking should be cleared after trade closes successfully"""
        symbol = 'SOL/USDC:USDC'
        
        # First trade
        state.add_trade({
            'symbol': symbol,
            'side': 'LONG',
            'entry_price': 100.0,
            'exit_price': None,
            'size': 1.0,
            'pnl': None,
            'status': 'OPEN'
        })
        
        old_position = {
            'mark_price': 0,
            'entry_price': 105.0,
            'size': 1.0,
            'side': 'LONG'
        }
        
        # Close first trade
        state._close_trade_in_history(symbol, old_position)
        
        # Add second trade
        state.add_trade({
            'symbol': symbol,
            'side': 'LONG',
            'entry_price': 110.0,
            'exit_price': None,
            'size': 1.0,
            'pnl': None,
            'status': 'OPEN'
        })
        
        # Close second trade - should also warn (because cleared after first)
        with patch('builtins.print') as mock_print:
            state._close_trade_in_history(symbol, old_position)
            
            warning_calls = [
                call for call in mock_print.call_args_list 
                if 'Using entry_price as exit_price fallback' in str(call)
            ]
            self.assertEqual(len(warning_calls), 1)


if __name__ == '__main__':
    unittest.main()
