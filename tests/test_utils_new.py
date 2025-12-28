"""
Tests for new utility functions: symbol normalization, tick-tolerant price comparison, 
and log throttling.
"""
import unittest
import datetime
from datetime import timezone
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import order_utils


class TestNormalizeSymbol(unittest.TestCase):
    """Test symbol normalization function"""
    
    def test_normalize_spot_symbol(self):
        """Test normalizing standard spot symbol"""
        self.assertEqual(order_utils.normalize_symbol("BTC/USDT"), "BTC/USDT")
    
    def test_normalize_futures_symbol(self):
        """Test normalizing futures symbol with suffix"""
        self.assertEqual(order_utils.normalize_symbol("XRP/USDT:USDT"), "XRP/USDT")
        self.assertEqual(order_utils.normalize_symbol("BTC/USDT:USDT"), "BTC/USDT")
        self.assertEqual(order_utils.normalize_symbol("SOL/USDT:USDT"), "SOL/USDT")
    
    def test_normalize_lowercase(self):
        """Test that lowercase is converted to uppercase"""
        self.assertEqual(order_utils.normalize_symbol("btc/usdt"), "BTC/USDT")
        self.assertEqual(order_utils.normalize_symbol("xrp/usdt:usdt"), "XRP/USDT")
    
    def test_normalize_mixed_case(self):
        """Test mixed case symbols"""
        self.assertEqual(order_utils.normalize_symbol("Btc/Usdt"), "BTC/USDT")
        self.assertEqual(order_utils.normalize_symbol("Eth/usdt:USDT"), "ETH/USDT")
    
    def test_normalize_none_and_empty(self):
        """Test handling of None and empty strings"""
        self.assertIsNone(order_utils.normalize_symbol(None))
        self.assertEqual(order_utils.normalize_symbol(""), "")


class TestPricesAreEqual(unittest.TestCase):
    """Test tick-tolerant price comparison function"""
    
    def test_exact_equal_prices(self):
        """Test exactly equal prices"""
        self.assertTrue(order_utils.prices_are_equal(100.0, 100.0, 0.01))
    
    def test_within_tick_tolerance(self):
        """Test prices within tick size tolerance"""
        # Tick size 0.01, prices differ by 0.005 - should be equal
        self.assertTrue(order_utils.prices_are_equal(100.0, 100.005, 0.01))
        self.assertTrue(order_utils.prices_are_equal(100.0, 99.995, 0.01))
    
    def test_within_percentage_tolerance(self):
        """Test prices within percentage tolerance"""
        # 0.1% of 100 = 0.1, prices differ by 0.1 - should be equal
        self.assertTrue(order_utils.prices_are_equal(100.0, 100.1, 0.01))
        self.assertTrue(order_utils.prices_are_equal(100.0, 99.9, 0.01))
    
    def test_outside_tolerance(self):
        """Test prices outside tolerance"""
        # 0.1% of 100 = 0.1, prices differ by more than that
        self.assertFalse(order_utils.prices_are_equal(100.0, 100.2, 0.01))
        self.assertFalse(order_utils.prices_are_equal(100.0, 99.8, 0.01))
    
    def test_large_price_difference(self):
        """Test clearly different prices"""
        self.assertFalse(order_utils.prices_are_equal(100.0, 110.0, 0.01))
        self.assertFalse(order_utils.prices_are_equal(100.0, 90.0, 0.01))
    
    def test_none_prices(self):
        """Test handling of None prices"""
        self.assertFalse(order_utils.prices_are_equal(None, 100.0, 0.01))
        self.assertFalse(order_utils.prices_are_equal(100.0, None, 0.01))
        self.assertFalse(order_utils.prices_are_equal(None, None, 0.01))
    
    def test_large_tick_size(self):
        """Test with larger tick size"""
        # Tick size 1.0, prices differ by 0.5 - should be equal
        self.assertTrue(order_utils.prices_are_equal(100.0, 100.5, 1.0))
        # But differ by more than tick - should not be equal
        self.assertFalse(order_utils.prices_are_equal(100.0, 102.0, 1.0))
    
    def test_small_prices(self):
        """Test with small prices (e.g., SHIB-like tokens)"""
        # For price 0.00001, 0.1% = 0.00000001
        # Tick size 0.00000001
        self.assertTrue(order_utils.prices_are_equal(0.00001, 0.0000100005, 0.00000001))
    
    def test_zero_tick_size_fallback(self):
        """Test that zero tick size falls back to small default"""
        # Should use default tiny tick size
        self.assertTrue(order_utils.prices_are_equal(100.0, 100.0, 0))


class TestLogThrottling(unittest.TestCase):
    """Test log throttling functionality"""
    
    def setUp(self):
        """Reset throttle state before each test"""
        order_utils._log_throttle_state = {}
    
    def test_first_log_always_allowed(self):
        """Test that first log for a category/symbol is always allowed"""
        should_log, suppressed = order_utils.should_log_throttled("test_category", "BTC/USDT")
        self.assertTrue(should_log)
        self.assertEqual(suppressed, 0)
    
    def test_second_immediate_log_throttled(self):
        """Test that second immediate log is throttled"""
        # First log - allowed
        order_utils.should_log_throttled("test_category", "BTC/USDT")
        
        # Second log - should be throttled
        should_log, suppressed = order_utils.should_log_throttled("test_category", "BTC/USDT")
        self.assertFalse(should_log)
    
    def test_different_category_not_throttled(self):
        """Test that different categories are tracked separately"""
        # Log first category
        order_utils.should_log_throttled("category_a", "BTC/USDT")
        
        # Different category should still be allowed
        should_log, suppressed = order_utils.should_log_throttled("category_b", "BTC/USDT")
        self.assertTrue(should_log)
    
    def test_different_symbol_not_throttled(self):
        """Test that different symbols are tracked separately"""
        # Log first symbol
        order_utils.should_log_throttled("test_category", "BTC/USDT")
        
        # Different symbol should still be allowed
        should_log, suppressed = order_utils.should_log_throttled("test_category", "ETH/USDT")
        self.assertTrue(should_log)
    
    def test_symbol_normalization_in_throttle(self):
        """Test that symbol is normalized for throttle key"""
        # Log with futures symbol format
        order_utils.should_log_throttled("test_category", "BTC/USDT:USDT")
        
        # Same symbol in spot format should be throttled
        should_log, suppressed = order_utils.should_log_throttled("test_category", "BTC/USDT")
        self.assertFalse(should_log)
    
    def test_suppressed_count_increments(self):
        """Test that suppressed count increments"""
        # First log
        order_utils.should_log_throttled("test_category", "BTC/USDT")
        
        # Suppress a few times
        order_utils.should_log_throttled("test_category", "BTC/USDT")
        order_utils.should_log_throttled("test_category", "BTC/USDT")
        order_utils.should_log_throttled("test_category", "BTC/USDT")
        
        # Check count (by manipulating time - this is a simplified test)
        # In real use, after interval, should_log would return True with suppressed count
        state = order_utils._log_throttle_state.get(("test_category", "BTC/USDT"))
        self.assertEqual(state["count"], 3)


class TestThrottledLogFunctions(unittest.TestCase):
    """Test the throttled log wrapper functions"""
    
    def setUp(self):
        """Reset throttle state before each test"""
        order_utils._log_throttle_state = {}
    
    def test_log_tp_sl_inconsistent_throttled_first_call(self):
        """Test that first call to log_tp_sl_inconsistent_throttled logs"""
        # Just verify it doesn't raise an exception
        order_utils.log_tp_sl_inconsistent_throttled("BTC/USDT", "LONG", 40000, 45000, 38000)
        
        # Verify state was created
        self.assertIn(("tp_sl_inconsistent", "BTC/USDT"), order_utils._log_throttle_state)
    
    def test_log_pending_order_active_throttled_first_call(self):
        """Test that first call to log_pending_order_active_throttled logs"""
        # Just verify it doesn't raise an exception
        order_utils.log_pending_order_active_throttled("12345", "ETH/USDT")
        
        # Verify state was created
        self.assertIn(("pending_order_active", "ETH/USDT"), order_utils._log_throttle_state)


if __name__ == '__main__':
    unittest.main()
