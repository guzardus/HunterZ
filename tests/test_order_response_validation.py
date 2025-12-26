"""
Unit tests for order response validation and safe_split helper

These tests cover:
- safe_split helper for None-safe string splitting
- _validate_order_response for validating exchange order responses
- Order placement with None/malformed responses
"""
import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import safe_split
from execution import _validate_order_response, _is_transient_error, HyperliquidClient
import state


class TestSafeSplit(unittest.TestCase):
    """Test safe_split helper function"""
    
    def test_safe_split_normal_string(self):
        """Test splitting a normal string"""
        result = safe_split("part1:part2:part3", ':')
        self.assertEqual(result, ['part1', 'part2', 'part3'])
    
    def test_safe_split_none_value(self):
        """Test splitting None returns empty list"""
        result = safe_split(None, ':')
        self.assertEqual(result, [])
    
    def test_safe_split_empty_string(self):
        """Test splitting empty string"""
        result = safe_split("", ':')
        self.assertEqual(result, [''])
    
    def test_safe_split_numeric_value(self):
        """Test splitting numeric value (converts to string)"""
        result = safe_split(12345, ':')
        self.assertEqual(result, ['12345'])
    
    def test_safe_split_with_maxsplit(self):
        """Test splitting with maxsplit limit"""
        result = safe_split("a:b:c:d", ':', maxsplit=2)
        self.assertEqual(result, ['a', 'b', 'c:d'])
    
    def test_safe_split_different_separator(self):
        """Test splitting with different separator"""
        result = safe_split("a-b-c", '-')
        self.assertEqual(result, ['a', 'b', 'c'])
    
    def test_safe_split_no_separator_found(self):
        """Test splitting when separator not found"""
        result = safe_split("abc", ':')
        self.assertEqual(result, ['abc'])
    
    def test_safe_split_dict_value(self):
        """Test splitting a dict (should convert to string)"""
        result = safe_split({'key': 'value'}, ':')
        # Dict converts to string representation
        self.assertIsInstance(result, list)
        self.assertTrue(len(result) >= 1)


class TestValidateOrderResponse(unittest.TestCase):
    """Test _validate_order_response function"""
    
    def test_valid_response_with_id(self):
        """Test valid response with 'id' field"""
        resp = {'id': '12345', 'status': 'open'}
        result = _validate_order_response(resp)
        self.assertEqual(result, resp)
    
    def test_valid_response_with_orderId(self):
        """Test valid response with 'orderId' field"""
        resp = {'orderId': '12345', 'status': 'open'}
        result = _validate_order_response(resp)
        self.assertEqual(result, resp)
    
    def test_valid_response_with_client_order_id(self):
        """Test valid response with 'client_order_id' field"""
        resp = {'client_order_id': '12345', 'status': 'open'}
        result = _validate_order_response(resp)
        self.assertEqual(result, resp)
    
    def test_valid_response_with_clientOrderId(self):
        """Test valid response with 'clientOrderId' field"""
        resp = {'clientOrderId': '12345', 'status': 'open'}
        result = _validate_order_response(resp)
        self.assertEqual(result, resp)
    
    def test_none_response(self):
        """Test None response returns None"""
        result = _validate_order_response(None)
        self.assertIsNone(result)
    
    def test_empty_dict_response(self):
        """Test empty dict response returns None"""
        result = _validate_order_response({})
        self.assertIsNone(result)
    
    def test_response_with_none_id(self):
        """Test response with None id field returns None"""
        resp = {'id': None, 'status': 'open'}
        result = _validate_order_response(resp)
        self.assertIsNone(result)
    
    def test_response_with_empty_id(self):
        """Test response with empty string id returns None"""
        resp = {'id': '', 'status': 'open'}
        result = _validate_order_response(resp)
        self.assertIsNone(result)
    
    def test_string_response(self):
        """Test string response returns None (not a dict)"""
        result = _validate_order_response("not a dict")
        self.assertIsNone(result)
    
    def test_list_response(self):
        """Test list response returns None"""
        result = _validate_order_response([{'id': '123'}])
        self.assertIsNone(result)
    
    def test_response_with_zero_id(self):
        """Test response with zero id returns None (falsy)"""
        resp = {'id': 0, 'status': 'open'}
        result = _validate_order_response(resp)
        self.assertIsNone(result)


class TestIsTransientError(unittest.TestCase):
    """Test _is_transient_error function"""
    
    def test_timeout_error(self):
        """Test timeout error is transient"""
        error = Exception("Connection timeout")
        result = _is_transient_error(error)
        self.assertTrue(result)
    
    def test_network_error(self):
        """Test network error is transient"""
        error = Exception("Network error occurred")
        result = _is_transient_error(error)
        self.assertTrue(result)
    
    def test_rate_limit_error(self):
        """Test rate limit error is transient"""
        error = Exception("Rate limit exceeded")
        result = _is_transient_error(error)
        self.assertTrue(result)
    
    def test_429_error(self):
        """Test 429 HTTP error is transient"""
        error = Exception("HTTP 429 Too Many Requests")
        result = _is_transient_error(error)
        self.assertTrue(result)
    
    def test_503_error(self):
        """Test 503 HTTP error is transient"""
        error = Exception("HTTP 503 Service Unavailable")
        result = _is_transient_error(error)
        self.assertTrue(result)
    
    def test_invalid_order_error(self):
        """Test invalid order error is NOT transient"""
        error = Exception("Invalid order: insufficient funds")
        result = _is_transient_error(error)
        self.assertFalse(result)
    
    def test_authentication_error(self):
        """Test authentication error is NOT transient"""
        error = Exception("Authentication failed")
        result = _is_transient_error(error)
        self.assertFalse(result)


class TestOrderPlacementWithValidation(unittest.TestCase):
    """Test order placement with validation"""
    
    def setUp(self):
        """Set up test fixtures"""
        state.bot_state.positions = {}
        state.bot_state.exchange_open_orders = []
        state.bot_state.pending_orders = {}
    
    @patch('execution.ccxt.hyperliquid')
    def test_place_limit_order_valid_response(self, mock_hyperliquid_class):
        """Test placing limit order with valid response"""
        mock_exchange = MagicMock()
        mock_hyperliquid_class.return_value = mock_exchange
        
        mock_exchange.create_order.return_value = {
            'id': '12345',
            'status': 'open',
            'type': 'limit'
        }
        
        client = HyperliquidClient()
        result = client.place_limit_order('BTC/USDC', 'buy', 0.1, 45000.0)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['id'], '12345')
    
    @patch('execution.ccxt.hyperliquid')
    def test_place_limit_order_none_response(self, mock_hyperliquid_class):
        """Test placing limit order with None response"""
        mock_exchange = MagicMock()
        mock_hyperliquid_class.return_value = mock_exchange
        
        mock_exchange.create_order.return_value = None
        
        client = HyperliquidClient()
        result = client.place_limit_order('BTC/USDC', 'buy', 0.1, 45000.0)
        
        self.assertIsNone(result)
    
    @patch('execution.ccxt.hyperliquid')
    def test_place_limit_order_missing_id(self, mock_hyperliquid_class):
        """Test placing limit order with response missing id"""
        mock_exchange = MagicMock()
        mock_hyperliquid_class.return_value = mock_exchange
        
        mock_exchange.create_order.return_value = {
            'status': 'open',
            'type': 'limit'
        }
        
        client = HyperliquidClient()
        result = client.place_limit_order('BTC/USDC', 'buy', 0.1, 45000.0)
        
        # Should return None because id is missing
        self.assertIsNone(result)
    
    @patch('execution.ccxt.hyperliquid')
    def test_place_stop_loss_valid_response(self, mock_hyperliquid_class):
        """Test placing stop loss with valid response"""
        mock_exchange = MagicMock()
        mock_hyperliquid_class.return_value = mock_exchange
        
        mock_exchange.create_order.return_value = {
            'id': 'sl_12345',
            'status': 'open',
            'type': 'STOP_MARKET'
        }
        
        client = HyperliquidClient()
        result = client.place_stop_loss('BTC/USDC', 'sell', 0.1, 43000.0)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['id'], 'sl_12345')
    
    @patch('execution.ccxt.hyperliquid')
    def test_place_stop_loss_none_response(self, mock_hyperliquid_class):
        """Test placing stop loss with None response"""
        mock_exchange = MagicMock()
        mock_hyperliquid_class.return_value = mock_exchange
        
        mock_exchange.create_order.return_value = None
        
        client = HyperliquidClient()
        result = client.place_stop_loss('BTC/USDC', 'sell', 0.1, 43000.0)
        
        self.assertIsNone(result)
    
    @patch('execution.ccxt.hyperliquid')
    def test_place_take_profit_valid_response(self, mock_hyperliquid_class):
        """Test placing take profit with valid response"""
        mock_exchange = MagicMock()
        mock_hyperliquid_class.return_value = mock_exchange
        
        mock_exchange.create_order.return_value = {
            'id': 'tp_12345',
            'status': 'open',
            'type': 'TAKE_PROFIT_MARKET'
        }
        
        client = HyperliquidClient()
        result = client.place_take_profit('BTC/USDC', 'sell', 0.1, 49000.0)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['id'], 'tp_12345')
    
    @patch('execution.ccxt.hyperliquid')
    def test_place_take_profit_none_response(self, mock_hyperliquid_class):
        """Test placing take profit with None response"""
        mock_exchange = MagicMock()
        mock_hyperliquid_class.return_value = mock_exchange
        
        mock_exchange.create_order.return_value = None
        
        client = HyperliquidClient()
        result = client.place_take_profit('BTC/USDC', 'sell', 0.1, 49000.0)
        
        self.assertIsNone(result)
    
    @patch('execution.ccxt.hyperliquid')
    def test_close_position_market_valid_response(self, mock_hyperliquid_class):
        """Test market close with valid response"""
        mock_exchange = MagicMock()
        mock_hyperliquid_class.return_value = mock_exchange
        
        mock_exchange.create_order.return_value = {
            'id': 'market_12345',
            'status': 'filled',
            'type': 'market'
        }
        
        client = HyperliquidClient()
        result = client.close_position_market('BTC/USDC', 'sell', 0.1, 'tp_breach')
        
        self.assertIsNotNone(result)
        self.assertEqual(result['id'], 'market_12345')
    
    @patch('execution.ccxt.hyperliquid')
    def test_close_position_market_none_response(self, mock_hyperliquid_class):
        """Test market close with None response"""
        mock_exchange = MagicMock()
        mock_hyperliquid_class.return_value = mock_exchange
        
        mock_exchange.create_order.return_value = None
        
        client = HyperliquidClient()
        result = client.close_position_market('BTC/USDC', 'sell', 0.1, 'tp_breach')
        
        self.assertIsNone(result)


class TestRetryLogic(unittest.TestCase):
    """Test retry logic for order placement"""
    
    @patch('execution.time.sleep')
    @patch('execution.ccxt.hyperliquid')
    def test_retry_on_transient_error(self, mock_hyperliquid_class, mock_sleep):
        """Test that transient errors trigger retries"""
        mock_exchange = MagicMock()
        mock_hyperliquid_class.return_value = mock_exchange
        
        # First call raises timeout, second succeeds
        mock_exchange.create_order.side_effect = [
            Exception("Connection timeout"),
            {'id': '12345', 'status': 'open'}
        ]
        
        client = HyperliquidClient()
        result = client.place_limit_order('BTC/USDC', 'buy', 0.1, 45000.0)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['id'], '12345')
        self.assertEqual(mock_exchange.create_order.call_count, 2)
        mock_sleep.assert_called()
    
    @patch('execution.time.sleep')
    @patch('execution.ccxt.hyperliquid')
    def test_no_retry_on_permanent_error(self, mock_hyperliquid_class, mock_sleep):
        """Test that permanent errors don't trigger retries"""
        mock_exchange = MagicMock()
        mock_hyperliquid_class.return_value = mock_exchange
        
        # Raise permanent error
        mock_exchange.create_order.side_effect = Exception("Insufficient funds")
        
        client = HyperliquidClient()
        result = client.place_limit_order('BTC/USDC', 'buy', 0.1, 45000.0)
        
        self.assertIsNone(result)
        # Should only call once (no retry for permanent error)
        self.assertEqual(mock_exchange.create_order.call_count, 1)
    
    @patch('execution.time.sleep')
    @patch('execution.ccxt.hyperliquid')
    def test_max_retries_exceeded(self, mock_hyperliquid_class, mock_sleep):
        """Test that max retries are enforced"""
        mock_exchange = MagicMock()
        mock_hyperliquid_class.return_value = mock_exchange
        
        # All calls raise timeout
        mock_exchange.create_order.side_effect = Exception("Connection timeout")
        
        client = HyperliquidClient()
        result = client.place_limit_order('BTC/USDC', 'buy', 0.1, 45000.0)
        
        self.assertIsNone(result)
        # Should call 3 times (MAX_ORDER_RETRIES)
        self.assertEqual(mock_exchange.create_order.call_count, 3)


if __name__ == '__main__':
    unittest.main()
