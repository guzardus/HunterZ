"""
Unit tests for TP/SL reconciliation logic
"""
import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import state


class TestTPSLReconciliationLogic(unittest.TestCase):
    """Test TP/SL reconciliation decision logic"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Reset bot state before each test
        state.bot_state.positions = {}
        state.bot_state.exchange_open_orders = []
        state.bot_state.pending_orders = {}
        state.bot_state.reconciliation_log = []
    
    def test_compute_position_tp_sl_with_both_orders(self):
        """Test computing TP/SL when both orders exist"""
        symbol = 'BTC/USDT'
        exchange_orders = [
            {
                'symbol': 'BTC/USDT',
                'type': 'STOP_MARKET',
                'reduceOnly': True,
                'stopPrice': 40000.0
            },
            {
                'symbol': 'BTC/USDT',
                'type': 'TAKE_PROFIT_MARKET',
                'reduceOnly': True,
                'stopPrice': 50000.0
            }
        ]
        
        result = state.compute_position_tp_sl(symbol, exchange_orders)
        
        self.assertEqual(result['stop_loss'], 40000.0)
        self.assertEqual(result['take_profit'], 50000.0)
    
    def test_compute_position_tp_sl_with_only_sl(self):
        """Test computing TP/SL when only SL exists"""
        symbol = 'ETH/USDT'
        exchange_orders = [
            {
                'symbol': 'ETH/USDT',
                'type': 'STOP_MARKET',
                'reduceOnly': True,
                'stopPrice': 2800.0
            }
        ]
        
        result = state.compute_position_tp_sl(symbol, exchange_orders)
        
        self.assertEqual(result['stop_loss'], 2800.0)
        self.assertIsNone(result['take_profit'])
    
    def test_compute_position_tp_sl_with_only_tp(self):
        """Test computing TP/SL when only TP exists"""
        symbol = 'SOL/USDT'
        exchange_orders = [
            {
                'symbol': 'SOL/USDT',
                'type': 'TAKE_PROFIT_MARKET',
                'reduceOnly': True,
                'stopPrice': 120.0
            }
        ]
        
        result = state.compute_position_tp_sl(symbol, exchange_orders)
        
        self.assertIsNone(result['stop_loss'])
        self.assertEqual(result['take_profit'], 120.0)
    
    def test_compute_position_tp_sl_no_orders(self):
        """Test computing TP/SL when no TP/SL orders exist"""
        symbol = 'BNB/USDT'
        exchange_orders = [
            {
                'symbol': 'BNB/USDT',
                'type': 'LIMIT',
                'reduceOnly': False
            }
        ]
        
        result = state.compute_position_tp_sl(symbol, exchange_orders)
        
        self.assertIsNone(result['stop_loss'])
        self.assertIsNone(result['take_profit'])
    
    def test_compute_position_tp_sl_different_symbol(self):
        """Test that TP/SL from different symbol is not used"""
        symbol = 'BTC/USDT'
        exchange_orders = [
            {
                'symbol': 'ETH/USDT',  # Different symbol
                'type': 'STOP_MARKET',
                'reduceOnly': True,
                'stopPrice': 2800.0
            }
        ]
        
        result = state.compute_position_tp_sl(symbol, exchange_orders)
        
        self.assertIsNone(result['stop_loss'])
        self.assertIsNone(result['take_profit'])
    
    def test_enrich_positions_with_tp_sl(self):
        """Test enriching positions with TP/SL from orders"""
        # Set up a position
        state.bot_state.positions['BTC/USDT'] = {
            'symbol': 'BTC/USDT',
            'side': 'LONG',
            'size': 0.1,
            'entry_price': 45000.0,
            'mark_price': 46000.0,
            'unrealized_pnl': 100.0,
            'leverage': 10,
            'take_profit': None,
            'stop_loss': None
        }
        
        # Set up exchange orders
        state.bot_state.exchange_open_orders = [
            {
                'symbol': 'BTC/USDT',
                'type': 'STOP_MARKET',
                'reduceOnly': True,
                'stopPrice': 43000.0
            },
            {
                'symbol': 'BTC/USDT',
                'type': 'TAKE_PROFIT_MARKET',
                'reduceOnly': True,
                'stopPrice': 49000.0
            }
        ]
        
        # Enrich positions
        state.enrich_positions_with_tp_sl()
        
        # Verify TP/SL were added
        position = state.bot_state.positions['BTC/USDT']
        self.assertEqual(position['stop_loss'], 43000.0)
        self.assertEqual(position['take_profit'], 49000.0)
    
    def test_enrich_positions_with_tp_sl_multiple_positions(self):
        """Test enriching multiple positions with their respective TP/SL"""
        # Set up multiple positions
        state.bot_state.positions['BTC/USDT'] = {
            'symbol': 'BTC/USDT',
            'side': 'LONG',
            'size': 0.1,
            'entry_price': 45000.0,
            'take_profit': None,
            'stop_loss': None
        }
        state.bot_state.positions['ETH/USDT'] = {
            'symbol': 'ETH/USDT',
            'side': 'SHORT',
            'size': 2.0,
            'entry_price': 3000.0,
            'take_profit': None,
            'stop_loss': None
        }
        
        # Set up exchange orders for both
        state.bot_state.exchange_open_orders = [
            {
                'symbol': 'BTC/USDT',
                'type': 'STOP_MARKET',
                'stopPrice': 43000.0
            },
            {
                'symbol': 'BTC/USDT',
                'type': 'TAKE_PROFIT_MARKET',
                'stopPrice': 49000.0
            },
            {
                'symbol': 'ETH/USDT',
                'type': 'STOP_MARKET',
                'stopPrice': 3100.0
            },
            {
                'symbol': 'ETH/USDT',
                'type': 'TAKE_PROFIT_MARKET',
                'stopPrice': 2800.0
            }
        ]
        
        # Enrich positions
        state.enrich_positions_with_tp_sl()
        
        # Verify both positions got correct TP/SL
        btc_position = state.bot_state.positions['BTC/USDT']
        self.assertEqual(btc_position['stop_loss'], 43000.0)
        self.assertEqual(btc_position['take_profit'], 49000.0)
        
        eth_position = state.bot_state.positions['ETH/USDT']
        self.assertEqual(eth_position['stop_loss'], 3100.0)
        self.assertEqual(eth_position['take_profit'], 2800.0)


if __name__ == '__main__':
    unittest.main()
