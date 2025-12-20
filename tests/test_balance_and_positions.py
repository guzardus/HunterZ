"""
Tests for wallet balance retrieval and account-wide position fetching
"""
import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution import BinanceClient
import state


class TestWalletBalanceRetrieval(unittest.TestCase):
    """Test wallet balance retrieval to prevent double-counting"""
    
    def setUp(self):
        """Set up test fixtures"""
        state.bot_state.positions = {}
        state.bot_state.total_balance = 0.0
    
    @patch('execution.ccxt.binance')
    def test_get_full_balance_returns_wallet_balance(self, mock_binance_class):
        """Test that get_full_balance returns wallet balance from info field"""
        # Set up mock exchange
        mock_exchange = MagicMock()
        mock_binance_class.return_value = mock_exchange
        
        # Mock fetch_balance to return Binance Futures format
        mock_exchange.fetch_balance.return_value = {
            'USDT': {
                'free': 5000.0,
                'used': 3331.18,
                'total': 8331.18,  # This is margin balance (includes unrealized P&L)
                'info': {
                    'walletBalance': '8000.00',  # This is actual wallet balance
                    'unrealizedProfit': '331.18'  # Unrealized P&L
                }
            }
        }
        
        # Create client
        client = BinanceClient()
        
        # Get balance
        balance = client.get_full_balance()
        
        # Verify that wallet balance is returned as 'total'
        self.assertEqual(balance['total'], 8000.0)
        self.assertEqual(balance['free'], 5000.0)
        self.assertEqual(balance['used'], 3331.18)
    
    @patch('execution.ccxt.binance')
    def test_get_full_balance_fallback_to_free(self, mock_binance_class):
        """Test that get_full_balance falls back to 'free' if walletBalance not available"""
        # Set up mock exchange
        mock_exchange = MagicMock()
        mock_binance_class.return_value = mock_exchange
        
        # Mock fetch_balance to return format without info field
        mock_exchange.fetch_balance.return_value = {
            'USDT': {
                'free': 5000.0,
                'used': 3000.0,
                'total': 8000.0
            }
        }
        
        # Create client
        client = BinanceClient()
        
        # Get balance
        balance = client.get_full_balance()
        
        # Verify that free balance is used as fallback
        self.assertEqual(balance['total'], 5000.0)
        self.assertEqual(balance['free'], 5000.0)


class TestAccountWidePositionFetching(unittest.TestCase):
    """Test that all positions are fetched and tracked, not just TRADING_PAIRS"""
    
    def setUp(self):
        """Set up test fixtures"""
        state.bot_state.positions = {}
        state.bot_state.exchange_open_orders = []
    
    @patch('execution.ccxt.binance')
    def test_get_all_positions_returns_all_active_positions(self, mock_binance_class):
        """Test that get_all_positions returns all positions with non-zero amounts"""
        # Set up mock exchange
        mock_exchange = MagicMock()
        mock_binance_class.return_value = mock_exchange
        
        # Mock fetch_positions to return multiple positions
        mock_exchange.fetch_positions.return_value = [
            {
                'symbol': 'BTC/USDT',
                'contracts': 0.5,
                'entryPrice': 45000.0,
                'markPrice': 46000.0,
                'unrealizedPnl': 500.0,
                'side': 'LONG'
            },
            {
                'symbol': 'ETH/USDT',
                'contracts': 2.0,
                'entryPrice': 2500.0,
                'markPrice': 2600.0,
                'unrealizedPnl': 200.0,
                'side': 'LONG'
            },
            {
                'symbol': 'XRP/USDT',  # Not in TRADING_PAIRS
                'contracts': 1000.0,
                'entryPrice': 0.5,
                'markPrice': 0.52,
                'unrealizedPnl': 20.0,
                'side': 'LONG'
            },
            {
                'symbol': 'DOGE/USDT',  # Closed position (0 contracts)
                'contracts': 0,
                'entryPrice': 0.0,
                'markPrice': 0.1,
                'unrealizedPnl': 0.0,
                'side': None
            }
        ]
        
        # Create client
        client = BinanceClient()
        
        # Get all positions
        positions = client.get_all_positions()
        
        # Verify that only active positions are returned (non-zero contracts)
        self.assertEqual(len(positions), 3)
        
        # Verify XRP position is included (not in TRADING_PAIRS)
        symbols = [p['symbol'] for p in positions]
        self.assertIn('XRP/USDT', symbols)
        
        # Verify DOGE is excluded (0 contracts)
        self.assertNotIn('DOGE/USDT', symbols)
    
    def test_update_position_handles_any_symbol(self):
        """Test that update_position can handle any symbol, not just TRADING_PAIRS"""
        # Create a position for a symbol not in TRADING_PAIRS
        position = {
            'symbol': 'MATIC/USDT',
            'contracts': 100.0,
            'entryPrice': 0.8,
            'markPrice': 0.85,
            'unrealizedPnl': 5.0,
            'side': 'LONG'
        }
        
        # Update position
        state.update_position('MATIC/USDT', position)
        
        # Verify position is stored in state
        self.assertIn('MATIC/USDT', state.bot_state.positions)
        self.assertEqual(state.bot_state.positions['MATIC/USDT']['size'], 100.0)
        self.assertEqual(state.bot_state.positions['MATIC/USDT']['entry_price'], 0.8)
    
    def test_closed_positions_removed_from_state(self):
        """Test that closed positions are removed from state"""
        # Add a position to state
        state.bot_state.positions['BTC/USDT'] = {
            'symbol': 'BTC/USDT',
            'side': 'LONG',
            'size': 0.5,
            'entry_price': 45000.0,
            'mark_price': 46000.0,
            'unrealized_pnl': 500.0
        }
        
        # Update with None (position closed)
        state.update_position('BTC/USDT', None)
        
        # Verify position is removed from state
        self.assertNotIn('BTC/USDT', state.bot_state.positions)
    
    def test_enrich_positions_with_tp_sl_works_with_any_symbol(self):
        """Test that enrich_positions_with_tp_sl works with positions from any symbol"""
        # Add positions for various symbols
        state.bot_state.positions['BTC/USDT'] = {
            'symbol': 'BTC/USDT',
            'side': 'LONG',
            'size': 0.5,
            'entry_price': 45000.0
        }
        state.bot_state.positions['MATIC/USDT'] = {  # Not in TRADING_PAIRS
            'symbol': 'MATIC/USDT',
            'side': 'SHORT',
            'size': 100.0,
            'entry_price': 0.8
        }
        
        # Add exchange orders with TP/SL
        state.bot_state.exchange_open_orders = [
            {
                'symbol': 'BTC/USDT',
                'type': 'TAKE_PROFIT_MARKET',
                'stopPrice': 50000.0,
                'reduceOnly': True
            },
            {
                'symbol': 'BTC/USDT',
                'type': 'STOP_MARKET',
                'stopPrice': 43000.0,
                'reduceOnly': True
            },
            {
                'symbol': 'MATIC/USDT',
                'type': 'TAKE_PROFIT_MARKET',
                'stopPrice': 0.75,
                'reduceOnly': True
            },
            {
                'symbol': 'MATIC/USDT',
                'type': 'STOP_MARKET',
                'stopPrice': 0.82,
                'reduceOnly': True
            }
        ]
        
        # Enrich positions with TP/SL
        state.enrich_positions_with_tp_sl()
        
        # Verify TP/SL are added for BTC
        self.assertEqual(state.bot_state.positions['BTC/USDT']['take_profit'], 50000.0)
        self.assertEqual(state.bot_state.positions['BTC/USDT']['stop_loss'], 43000.0)
        
        # Verify TP/SL are added for MATIC (not in TRADING_PAIRS)
        self.assertEqual(state.bot_state.positions['MATIC/USDT']['take_profit'], 0.75)
        self.assertEqual(state.bot_state.positions['MATIC/USDT']['stop_loss'], 0.82)


if __name__ == '__main__':
    unittest.main()
