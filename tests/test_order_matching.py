"""
Unit tests for order matching functionality (idempotent TP/SL placement).

These tests verify that:
1. approx_equal correctly compares values within tolerance
2. order_matches_target correctly identifies matching orders
3. Existing matching orders are not replaced
"""
import unittest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution import approx_equal, order_matches_target, PRICE_TOLERANCE_PCT, QUANTITY_TOLERANCE_PCT


class TestApproxEqual(unittest.TestCase):
    """Test approximate equality function"""
    
    def test_exact_match(self):
        """Exact values should match"""
        self.assertTrue(approx_equal(100.0, 100.0))
    
    def test_within_tolerance(self):
        """Values within tolerance should match"""
        # 1% tolerance
        self.assertTrue(approx_equal(100.0, 100.5, pct_tol=0.01))
        self.assertTrue(approx_equal(100.0, 99.5, pct_tol=0.01))
    
    def test_outside_tolerance(self):
        """Values outside tolerance should not match"""
        # 1% tolerance, 2% difference
        self.assertFalse(approx_equal(100.0, 102.0, pct_tol=0.01))
        self.assertFalse(approx_equal(100.0, 98.0, pct_tol=0.01))
    
    def test_zero_values(self):
        """Both zeros should match"""
        self.assertTrue(approx_equal(0, 0))
    
    def test_one_zero_value(self):
        """If one value is zero and other is not, should not match"""
        self.assertFalse(approx_equal(0, 100.0))
        self.assertFalse(approx_equal(100.0, 0))
    
    def test_negative_values(self):
        """Should work with negative values"""
        self.assertTrue(approx_equal(-100.0, -100.5, pct_tol=0.01))
    
    def test_small_values(self):
        """Should work with small values"""
        self.assertTrue(approx_equal(0.001, 0.00101, pct_tol=0.01))
    
    def test_large_values(self):
        """Should work with large values"""
        self.assertTrue(approx_equal(1000000, 1005000, pct_tol=0.01))


class TestOrderMatchesTarget(unittest.TestCase):
    """Test order matching function"""
    
    def test_matching_order_with_stop_price(self):
        """Order with matching stopPrice should match"""
        order = {
            'stopPrice': 45000.0,
            'amount': 0.1
        }
        self.assertTrue(order_matches_target(order, 45000.0, 0.1))
    
    def test_matching_order_with_regular_price(self):
        """Order with matching regular price should match"""
        order = {
            'price': 45000.0,
            'amount': 0.1
        }
        self.assertTrue(order_matches_target(order, 45000.0, 0.1))
    
    def test_slightly_different_price_within_tolerance(self):
        """Slightly different price within tolerance should match"""
        order = {
            'stopPrice': 45010.0,  # 0.022% difference
            'amount': 0.1
        }
        self.assertTrue(order_matches_target(order, 45000.0, 0.1, price_tol=0.001))
    
    def test_slightly_different_qty_within_tolerance(self):
        """Slightly different quantity within tolerance should match"""
        order = {
            'stopPrice': 45000.0,
            'amount': 0.1005  # 0.5% difference
        }
        self.assertTrue(order_matches_target(order, 45000.0, 0.1, qty_tol=0.01))
    
    def test_price_outside_tolerance(self):
        """Price outside tolerance should not match"""
        order = {
            'stopPrice': 45100.0,  # 0.22% difference
            'amount': 0.1
        }
        self.assertFalse(order_matches_target(order, 45000.0, 0.1, price_tol=0.001))
    
    def test_qty_outside_tolerance(self):
        """Quantity outside tolerance should not match"""
        order = {
            'stopPrice': 45000.0,
            'amount': 0.12  # 20% difference
        }
        self.assertFalse(order_matches_target(order, 45000.0, 0.1, qty_tol=0.01))
    
    def test_none_order(self):
        """None order should not match"""
        self.assertFalse(order_matches_target(None, 45000.0, 0.1))
    
    def test_empty_order(self):
        """Empty order should not match"""
        self.assertFalse(order_matches_target({}, 45000.0, 0.1))
    
    def test_zero_price_order(self):
        """Order with zero price should not match"""
        order = {
            'stopPrice': 0,
            'amount': 0.1
        }
        self.assertFalse(order_matches_target(order, 45000.0, 0.1))
    
    def test_zero_amount_order(self):
        """Order with zero amount should not match"""
        order = {
            'stopPrice': 45000.0,
            'amount': 0
        }
        self.assertFalse(order_matches_target(order, 45000.0, 0.1))
    
    def test_uses_remaining_if_amount_missing(self):
        """Should use 'remaining' field if 'amount' is missing"""
        order = {
            'stopPrice': 45000.0,
            'remaining': 0.1
        }
        self.assertTrue(order_matches_target(order, 45000.0, 0.1))
    
    def test_string_values_converted(self):
        """String values should be properly converted to float"""
        order = {
            'stopPrice': '45000.0',
            'amount': '0.1'
        }
        # Should not raise, but may not match if string conversion fails
        result = order_matches_target(order, 45000.0, 0.1)
        # String '45000.0' and '0.1' should convert to float properly
        self.assertTrue(result)


class TestDefaultTolerances(unittest.TestCase):
    """Test that default tolerances are reasonable"""
    
    def test_price_tolerance_value(self):
        """Price tolerance should be 0.1%"""
        self.assertEqual(PRICE_TOLERANCE_PCT, 0.001)
    
    def test_quantity_tolerance_value(self):
        """Quantity tolerance should be 1%"""
        self.assertEqual(QUANTITY_TOLERANCE_PCT, 0.01)


if __name__ == '__main__':
    unittest.main()
