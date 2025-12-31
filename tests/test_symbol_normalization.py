"""
Unit tests for symbol normalization and TP/SL order matching improvements.

These tests verify that:
1. normalize_symbol correctly handles different symbol formats
2. get_tp_sl_orders_for_position can match orders with different symbol formats
3. Order type detection handles various exchange formats
"""
import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import normalize_symbol


class TestNormalizeSymbol(unittest.TestCase):
    """Test symbol normalization function"""
    
    def test_normalize_with_settlement_suffix(self):
        """Symbol with settlement suffix should have it stripped"""
        self.assertEqual(normalize_symbol('BTC/USDC:USDC'), 'BTC/USDC')
    
    def test_normalize_without_suffix(self):
        """Symbol without suffix should remain unchanged"""
        self.assertEqual(normalize_symbol('BTC/USDC'), 'BTC/USDC')
    
    def test_normalize_simple_symbol(self):
        """Simple symbol without slash should remain unchanged"""
        self.assertEqual(normalize_symbol('BTCUSDC'), 'BTCUSDC')
    
    def test_normalize_with_whitespace(self):
        """Whitespace should be stripped"""
        self.assertEqual(normalize_symbol('  BTC/USDC:USDC  '), 'BTC/USDC')
    
    def test_normalize_none(self):
        """None should return None"""
        self.assertIsNone(normalize_symbol(None))
    
    def test_normalize_empty_string(self):
        """Empty string should return empty string"""
        self.assertEqual(normalize_symbol(''), '')
    
    def test_normalize_eth_symbol(self):
        """ETH symbol with suffix should be normalized"""
        self.assertEqual(normalize_symbol('ETH/USDC:USDC'), 'ETH/USDC')
    
    def test_normalize_sol_symbol(self):
        """SOL symbol with suffix should be normalized"""
        self.assertEqual(normalize_symbol('SOL/USDC:USDC'), 'SOL/USDC')
    
    def test_matching_normalized_symbols(self):
        """Different formats should normalize to same value"""
        norm1 = normalize_symbol('BTC/USDC:USDC')
        norm2 = normalize_symbol('BTC/USDC')
        self.assertEqual(norm1, norm2)


class TestGetTPSLOrdersSymbolMatching(unittest.TestCase):
    """Test TP/SL order matching with different symbol formats"""
    
    @patch('execution.ccxt')
    def test_match_orders_with_suffix_position(self, mock_ccxt):
        """Orders should match position even when symbol formats differ"""
        from execution import HyperliquidClient
        
        # Setup mock exchange
        mock_exchange = MagicMock()
        mock_ccxt.hyperliquid.return_value = mock_exchange
        
        # Create orders with "BTC/USDC" format (no suffix)
        mock_exchange.fetch_open_orders.return_value = [
            {
                'id': 'sl_order_1',
                'symbol': 'BTC/USDC',  # No :USDC suffix
                'type': 'STOP_MARKET',
                'reduceOnly': True,
                'stopPrice': 43000.0,
                'amount': 0.1
            },
            {
                'id': 'tp_order_1',
                'symbol': 'BTC/USDC',  # No :USDC suffix
                'type': 'TAKE_PROFIT_MARKET',
                'reduceOnly': True,
                'stopPrice': 49000.0,
                'amount': 0.1
            }
        ]
        
        client = HyperliquidClient()
        
        # Query with "BTC/USDC:USDC" format (with suffix)
        result = client.get_tp_sl_orders_for_position('BTC/USDC:USDC')
        
        # Should match despite format difference
        self.assertEqual(len(result['sl_orders']), 1)
        self.assertEqual(len(result['tp_orders']), 1)
        self.assertEqual(result['sl_orders'][0]['id'], 'sl_order_1')
        self.assertEqual(result['tp_orders'][0]['id'], 'tp_order_1')
    
    @patch('execution.ccxt')
    def test_match_orders_same_format(self, mock_ccxt):
        """Orders should match when symbol formats are same"""
        from execution import HyperliquidClient
        
        mock_exchange = MagicMock()
        mock_ccxt.hyperliquid.return_value = mock_exchange
        
        mock_exchange.fetch_open_orders.return_value = [
            {
                'id': 'sl_order_1',
                'symbol': 'ETH/USDC',
                'type': 'STOP_MARKET',
                'reduceOnly': True,
                'stopPrice': 2800.0,
                'amount': 1.0
            }
        ]
        
        client = HyperliquidClient()
        result = client.get_tp_sl_orders_for_position('ETH/USDC')
        
        self.assertEqual(len(result['sl_orders']), 1)
        self.assertEqual(result['sl_orders'][0]['id'], 'sl_order_1')
    
    @patch('execution.ccxt')
    def test_no_match_different_base_asset(self, mock_ccxt):
        """Orders for different base asset should not match"""
        from execution import HyperliquidClient
        
        mock_exchange = MagicMock()
        mock_ccxt.hyperliquid.return_value = mock_exchange
        
        mock_exchange.fetch_open_orders.return_value = [
            {
                'id': 'sl_order_1',
                'symbol': 'ETH/USDC',
                'type': 'STOP_MARKET',
                'reduceOnly': True,
                'stopPrice': 2800.0,
                'amount': 1.0
            }
        ]
        
        client = HyperliquidClient()
        result = client.get_tp_sl_orders_for_position('BTC/USDC:USDC')
        
        # Should not match ETH orders for BTC position
        self.assertEqual(result['sl_orders'], [])
        self.assertEqual(result['tp_orders'], [])


class TestOrderTypeDetection(unittest.TestCase):
    """Test detection of various TP/SL order types"""
    
    @patch('execution.ccxt')
    def test_detect_stop_market_uppercase(self, mock_ccxt):
        """STOP_MARKET order type should be detected as SL"""
        from execution import HyperliquidClient
        
        mock_exchange = MagicMock()
        mock_ccxt.hyperliquid.return_value = mock_exchange
        
        mock_exchange.fetch_open_orders.return_value = [
            {
                'id': 'sl_1',
                'symbol': 'BTC/USDC',
                'type': 'STOP_MARKET',
                'reduceOnly': True,
                'stopPrice': 43000.0,
                'amount': 0.1
            }
        ]
        
        client = HyperliquidClient()
        result = client.get_tp_sl_orders_for_position('BTC/USDC')
        
        self.assertEqual(len(result['sl_orders']), 1)
        self.assertEqual(result['tp_orders'], [])
    
    @patch('execution.ccxt')
    def test_detect_stop_market_lowercase(self, mock_ccxt):
        """stop_market order type should be detected as SL"""
        from execution import HyperliquidClient
        
        mock_exchange = MagicMock()
        mock_ccxt.hyperliquid.return_value = mock_exchange
        
        mock_exchange.fetch_open_orders.return_value = [
            {
                'id': 'sl_1',
                'symbol': 'BTC/USDC',
                'type': 'stop_market',
                'reduceOnly': True,
                'stopPrice': 43000.0,
                'amount': 0.1
            }
        ]
        
        client = HyperliquidClient()
        result = client.get_tp_sl_orders_for_position('BTC/USDC')
        
        self.assertEqual(len(result['sl_orders']), 1)
    
    @patch('execution.ccxt')
    def test_detect_take_profit_market(self, mock_ccxt):
        """TAKE_PROFIT_MARKET order type should be detected as TP"""
        from execution import HyperliquidClient
        
        mock_exchange = MagicMock()
        mock_ccxt.hyperliquid.return_value = mock_exchange
        
        mock_exchange.fetch_open_orders.return_value = [
            {
                'id': 'tp_1',
                'symbol': 'BTC/USDC',
                'type': 'TAKE_PROFIT_MARKET',
                'reduceOnly': True,
                'stopPrice': 49000.0,
                'amount': 0.1
            }
        ]
        
        client = HyperliquidClient()
        result = client.get_tp_sl_orders_for_position('BTC/USDC')
        
        self.assertEqual(result['sl_orders'], [])
        self.assertEqual(len(result['tp_orders']), 1)
    
    @patch('execution.ccxt')
    def test_detect_stop_limit(self, mock_ccxt):
        """STOP_LIMIT order type should be detected as SL"""
        from execution import HyperliquidClient
        
        mock_exchange = MagicMock()
        mock_ccxt.hyperliquid.return_value = mock_exchange
        
        mock_exchange.fetch_open_orders.return_value = [
            {
                'id': 'sl_1',
                'symbol': 'BTC/USDC',
                'type': 'STOP_LIMIT',
                'reduceOnly': True,
                'stopPrice': 43000.0,
                'price': 42900.0,
                'amount': 0.1
            }
        ]
        
        client = HyperliquidClient()
        result = client.get_tp_sl_orders_for_position('BTC/USDC')
        
        self.assertEqual(len(result['sl_orders']), 1)
    
    @patch('execution.ccxt')
    def test_detect_order_with_stop_price_only(self, mock_ccxt):
        """Order with stopPrice and reduceOnly but generic type should be detected"""
        from execution import HyperliquidClient
        
        mock_exchange = MagicMock()
        mock_ccxt.hyperliquid.return_value = mock_exchange
        
        # Some exchanges might return 'STOP' instead of 'STOP_MARKET'
        mock_exchange.fetch_open_orders.return_value = [
            {
                'id': 'sl_1',
                'symbol': 'BTC/USDC',
                'type': 'STOP',
                'reduceOnly': True,
                'stopPrice': 43000.0,
                'amount': 0.1
            }
        ]
        
        client = HyperliquidClient()
        result = client.get_tp_sl_orders_for_position('BTC/USDC')
        
        # Should detect as SL because 'STOP' contains 'STOP' and not 'TAKE_PROFIT'
        self.assertEqual(len(result['sl_orders']), 1)
    
    @patch('execution.ccxt')
    def test_skip_non_reduce_only_limit_order(self, mock_ccxt):
        """Regular limit orders (not reduce-only) should not be detected as TP/SL"""
        from execution import HyperliquidClient
        
        mock_exchange = MagicMock()
        mock_ccxt.hyperliquid.return_value = mock_exchange
        
        mock_exchange.fetch_open_orders.return_value = [
            {
                'id': 'limit_1',
                'symbol': 'BTC/USDC',
                'type': 'LIMIT',
                'reduceOnly': False,
                'price': 45000.0,
                'amount': 0.1
            }
        ]
        
        client = HyperliquidClient()
        result = client.get_tp_sl_orders_for_position('BTC/USDC')
        
        # Regular limit order should not be detected as TP/SL
        self.assertEqual(result['sl_orders'], [])
        self.assertEqual(result['tp_orders'], [])


class TestReconciliationSafetyCheck(unittest.TestCase):
    """Test the safety check that prevents double placement"""
    
    @patch('main.state')
    @patch('main.config')
    def test_recent_placement_defers_reconciliation(self, mock_config, mock_state):
        """If TP/SL was placed recently, reconciliation should be deferred"""
        import datetime
        from main import reconcile_position_tp_sl
        
        mock_config.TP_SL_QUANTITY_TOLERANCE = 0.01
        mock_config.RR_RATIO = 2.0
        mock_config.TP_SL_PLACEMENT_COOLDOWN_SECONDS = 30  # Use the config constant
        
        # Create a mock client
        mock_client = MagicMock()
        mock_client.exchange.price_to_precision.side_effect = lambda s, p: p
        mock_client.exchange.amount_to_precision.side_effect = lambda s, a: a
        
        # Simulate no existing TP/SL orders
        mock_client.get_tp_sl_orders_for_position.return_value = {
            'sl_orders': [],
            'tp_orders': []
        }
        
        position = {
            'contracts': 0.1,
            'entryPrice': 45000.0
        }
        
        # Simulate a pending order with recent TP/SL placement (5 seconds ago)
        recent_time = (datetime.datetime.now() - datetime.timedelta(seconds=5)).isoformat()
        pending_order = {
            'order_id': 'test_order',
            'params': {
                'stop_loss': 43000.0,
                'take_profit': 49000.0
            },
            'last_tp_sl_placement': recent_time
        }
        
        # Mock bot_state
        mock_state.bot_state = MagicMock()
        
        result = reconcile_position_tp_sl(mock_client, 'BTC/USDC', position, pending_order)
        
        # Should return True (success) without placing new orders
        self.assertTrue(result)
        
        # Verify that place_sl_tp_orders was NOT called (deferred)
        mock_client.place_sl_tp_orders.assert_not_called()
        mock_client.place_stop_loss.assert_not_called()
        mock_client.place_take_profit.assert_not_called()


if __name__ == '__main__':
    unittest.main()
