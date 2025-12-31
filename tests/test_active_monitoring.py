"""
Unit tests for active TP/SL monitoring functionality
"""
import unittest
from unittest.mock import Mock, MagicMock, patch, call
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import state
import config
from main import monitor_and_close_positions


class TestActiveMonitoring(unittest.TestCase):
    """Test active TP/SL monitoring logic"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Reset bot state before each test
        state.bot_state.positions = {}
        state.bot_state.exchange_open_orders = []
        state.bot_state.reconciliation_log = []
        
        # Create mock client
        self.mock_client = Mock()
        self.mock_client.exchange = Mock()
        self.mock_client.exchange.amount_to_precision = Mock(side_effect=lambda s, a: a)
        self.mock_client.get_tp_sl_orders_for_position = Mock(return_value={'sl_order': None, 'tp_order': None})
        self.mock_client.cancel_order = Mock(return_value=True)
        self.mock_client.close_position_market = Mock(return_value={'id': '12345'})
    
    def test_monitoring_disabled(self):
        """Test that monitoring is skipped when disabled"""
        with patch.object(config, 'ENABLE_ACTIVE_TP_SL_MONITORING', False):
            state.bot_state.positions = {
                'BTC/USDT': {
                    'symbol': 'BTC/USDT',
                    'side': 'LONG',
                    'size': 0.01,
                    'entry_price': 40000.0,
                    'mark_price': 50000.0,
                    'take_profit': 41000.0,
                    'stop_loss': 39000.0
                }
            }
            
            monitor_and_close_positions(self.mock_client)
            
            # Should not close any positions
            self.mock_client.close_position_market.assert_not_called()
    
    def test_long_position_tp_breach(self):
        """Test closing LONG position when TP is breached"""
        state.bot_state.positions = {
            'BTC/USDT': {
                'symbol': 'BTC/USDT',
                'side': 'LONG',
                'size': 0.01,
                'entry_price': 40000.0,
                'mark_price': 41500.0,  # Above TP
                'take_profit': 41000.0,
                'stop_loss': 39000.0
            }
        }
        
        monitor_and_close_positions(self.mock_client)
        
        # Should close with sell order
        self.mock_client.close_position_market.assert_called_once_with(
            'BTC/USDT', 'sell', 0.01, 'tp_breach'
        )
        
        # Should log the forced closure
        self.assertEqual(len(state.bot_state.reconciliation_log), 1)
        log_entry = state.bot_state.reconciliation_log[0]
        self.assertEqual(log_entry['action'], 'forced_closure')
        self.assertEqual(log_entry['reason'], 'tp_breach')
    
    def test_long_position_sl_breach(self):
        """Test closing LONG position when SL is breached"""
        state.bot_state.positions = {
            'ETH/USDT': {
                'symbol': 'ETH/USDT',
                'side': 'LONG',
                'size': 1.0,
                'entry_price': 3000.0,
                'mark_price': 2950.0,  # Below SL
                'take_profit': 3100.0,
                'stop_loss': 2980.0
            }
        }
        
        monitor_and_close_positions(self.mock_client)
        
        # Should close with sell order
        self.mock_client.close_position_market.assert_called_once_with(
            'ETH/USDT', 'sell', 1.0, 'sl_breach'
        )
        
        # Should log the forced closure
        log_entry = state.bot_state.reconciliation_log[0]
        self.assertEqual(log_entry['reason'], 'sl_breach')
    
    def test_short_position_tp_breach(self):
        """Test closing SHORT position when TP is breached"""
        state.bot_state.positions = {
            'SOL/USDT': {
                'symbol': 'SOL/USDT',
                'side': 'SHORT',
                'size': 10.0,
                'entry_price': 100.0,
                'mark_price': 98.0,  # Below TP (profit for short)
                'take_profit': 99.0,
                'stop_loss': 101.0
            }
        }
        
        monitor_and_close_positions(self.mock_client)
        
        # Should close with buy order (opposite of SHORT)
        self.mock_client.close_position_market.assert_called_once_with(
            'SOL/USDT', 'buy', 10.0, 'tp_breach'
        )
    
    def test_short_position_sl_breach(self):
        """Test closing SHORT position when SL is breached"""
        state.bot_state.positions = {
            'BNB/USDT': {
                'symbol': 'BNB/USDT',
                'side': 'SHORT',
                'size': 5.0,
                'entry_price': 300.0,
                'mark_price': 305.0,  # Above SL (loss for short)
                'take_profit': 290.0,
                'stop_loss': 303.0
            }
        }
        
        monitor_and_close_positions(self.mock_client)
        
        # Should close with buy order
        self.mock_client.close_position_market.assert_called_once_with(
            'BNB/USDT', 'buy', 5.0, 'sl_breach'
        )
    
    def test_no_breach(self):
        """Test that position is NOT closed when no breach occurs"""
        state.bot_state.positions = {
            'BTC/USDT': {
                'symbol': 'BTC/USDT',
                'side': 'LONG',
                'size': 0.01,
                'entry_price': 40000.0,
                'mark_price': 40500.0,  # Between SL and TP
                'take_profit': 41000.0,
                'stop_loss': 39000.0
            }
        }
        
        monitor_and_close_positions(self.mock_client)
        
        # Should not close position
        self.mock_client.close_position_market.assert_not_called()
    
    def test_position_without_tp_sl(self):
        """Test that position without TP/SL is skipped"""
        state.bot_state.positions = {
            'ADA/USDT': {
                'symbol': 'ADA/USDT',
                'side': 'LONG',
                'size': 100.0,
                'entry_price': 0.5,
                'mark_price': 0.6,
                'take_profit': None,
                'stop_loss': None
            }
        }
        
        monitor_and_close_positions(self.mock_client)
        
        # Should not close position
        self.mock_client.close_position_market.assert_not_called()
    
    def test_cancel_existing_orders_before_close(self):
        """Test that existing TP/SL orders are cancelled before closing"""
        state.bot_state.positions = {
            'BTC/USDT': {
                'symbol': 'BTC/USDT',
                'side': 'LONG',
                'size': 0.01,
                'entry_price': 40000.0,
                'mark_price': 41500.0,  # Above TP
                'take_profit': 41000.0,
                'stop_loss': 39000.0
            }
        }
        
        # Mock existing orders (now returns lists)
        self.mock_client.get_tp_sl_orders_for_position.return_value = {
            'sl_orders': [{'id': 'sl_123'}],
            'tp_orders': [{'id': 'tp_456'}]
        }
        
        monitor_and_close_positions(self.mock_client)
        
        # Should cancel both orders
        self.assertEqual(self.mock_client.cancel_order.call_count, 2)
        self.mock_client.cancel_order.assert_any_call('BTC/USDT', 'sl_123')
        self.mock_client.cancel_order.assert_any_call('BTC/USDT', 'tp_456')
        
        # Should still close position
        self.mock_client.close_position_market.assert_called_once()
    
    def test_pnl_calculation_long(self):
        """Test PnL calculation for LONG position"""
        state.bot_state.positions = {
            'BTC/USDT': {
                'symbol': 'BTC/USDT',
                'side': 'LONG',
                'size': 0.1,
                'entry_price': 40000.0,
                'mark_price': 41000.0,  # TP breach
                'take_profit': 41000.0,
                'stop_loss': 39000.0
            }
        }
        
        monitor_and_close_positions(self.mock_client)
        
        # Check logged PnL
        log_entry = state.bot_state.reconciliation_log[0]
        expected_pnl = (41000.0 - 40000.0) * 0.1  # 100 USDT
        self.assertEqual(log_entry['details']['pnl'], expected_pnl)
    
    def test_pnl_calculation_short(self):
        """Test PnL calculation for SHORT position"""
        state.bot_state.positions = {
            'SOL/USDT': {
                'symbol': 'SOL/USDT',
                'side': 'SHORT',
                'size': 10.0,
                'entry_price': 100.0,
                'mark_price': 99.0,  # TP breach
                'take_profit': 99.0,
                'stop_loss': 101.0
            }
        }
        
        monitor_and_close_positions(self.mock_client)
        
        # Check logged PnL
        log_entry = state.bot_state.reconciliation_log[0]
        expected_pnl = (100.0 - 99.0) * 10.0  # 10 USDT
        self.assertEqual(log_entry['details']['pnl'], expected_pnl)
    
    def test_multiple_positions(self):
        """Test monitoring multiple positions"""
        state.bot_state.positions = {
            'BTC/USDT': {
                'symbol': 'BTC/USDT',
                'side': 'LONG',
                'size': 0.01,
                'entry_price': 40000.0,
                'mark_price': 41500.0,  # TP breach
                'take_profit': 41000.0,
                'stop_loss': 39000.0
            },
            'ETH/USDT': {
                'symbol': 'ETH/USDT',
                'side': 'LONG',
                'size': 1.0,
                'entry_price': 3000.0,
                'mark_price': 3050.0,  # No breach
                'take_profit': 3100.0,
                'stop_loss': 2980.0
            },
            'SOL/USDT': {
                'symbol': 'SOL/USDT',
                'side': 'SHORT',
                'size': 10.0,
                'entry_price': 100.0,
                'mark_price': 102.0,  # SL breach
                'take_profit': 99.0,
                'stop_loss': 101.0
            }
        }
        
        monitor_and_close_positions(self.mock_client)
        
        # Should close 2 positions (BTC TP breach, SOL SL breach)
        self.assertEqual(self.mock_client.close_position_market.call_count, 2)
        
        # Verify correct closures
        calls = self.mock_client.close_position_market.call_args_list
        call_symbols = [call[0][0] for call in calls]
        self.assertIn('BTC/USDT', call_symbols)
        self.assertIn('SOL/USDT', call_symbols)
    
    def test_error_handling_continues_monitoring(self):
        """Test that error in one position doesn't stop monitoring others"""
        state.bot_state.positions = {
            'BTC/USDT': {
                'symbol': 'BTC/USDT',
                'side': 'LONG',
                'size': 0.01,
                'entry_price': 40000.0,
                'mark_price': 41500.0,
                'take_profit': 41000.0,
                'stop_loss': 39000.0
            },
            'ETH/USDT': {
                'symbol': 'ETH/USDT',
                'side': 'LONG',
                'size': 1.0,
                'entry_price': 3000.0,
                'mark_price': 2950.0,  # SL breach
                'take_profit': 3100.0,
                'stop_loss': 2980.0
            }
        }
        
        # Make first close fail
        self.mock_client.close_position_market.side_effect = [
            Exception("Network error"),
            {'id': '67890'}
        ]
        
        monitor_and_close_positions(self.mock_client)
        
        # Should attempt to close both positions
        self.assertEqual(self.mock_client.close_position_market.call_count, 2)
    
    def test_forced_closure_log_structure(self):
        """Test that forced closure log has correct structure"""
        state.bot_state.positions = {
            'BTC/USDT': {
                'symbol': 'BTC/USDT',
                'side': 'LONG',
                'size': 0.01,
                'entry_price': 40000.0,
                'mark_price': 41500.0,
                'take_profit': 41000.0,
                'stop_loss': 39000.0
            }
        }
        
        monitor_and_close_positions(self.mock_client)
        
        # Check log entry structure
        log_entry = state.bot_state.reconciliation_log[0]
        self.assertIn('timestamp', log_entry)
        self.assertEqual(log_entry['action'], 'forced_closure')
        self.assertEqual(log_entry['symbol'], 'BTC/USDT')
        self.assertEqual(log_entry['reason'], 'tp_breach')
        self.assertIn('details', log_entry)
        
        details = log_entry['details']
        self.assertIn('side', details)
        self.assertIn('size', details)
        self.assertIn('entry_price', details)
        self.assertIn('mark_price', details)
        self.assertIn('take_profit', details)
        self.assertIn('stop_loss', details)
        self.assertIn('pnl', details)
        self.assertIn('market_order_id', details)


class TestClosePositionMarket(unittest.TestCase):
    """Test close_position_market method in BinanceClient"""
    
    def test_close_position_market_creates_reduce_only_order(self):
        """Test that close_position_market creates a reduceOnly market order"""
        from execution import BinanceClient
        
        client = BinanceClient()
        client.exchange = Mock()
        client.exchange.create_order = Mock(return_value={'id': '12345', 'status': 'closed'})
        
        result = client.close_position_market('BTC/USDT', 'sell', 0.01, 'tp_breach')
        
        # Should call create_order with correct parameters
        client.exchange.create_order.assert_called_once_with(
            'BTC/USDT', 'market', 'sell', 0.01, params={'reduceOnly': True}
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result['id'], '12345')
    
    def test_close_position_market_handles_error(self):
        """Test that close_position_market handles errors gracefully"""
        from execution import BinanceClient
        
        client = BinanceClient()
        client.exchange = Mock()
        client.exchange.create_order = Mock(side_effect=Exception("API error"))
        
        result = client.close_position_market('ETH/USDT', 'buy', 1.0, 'sl_breach')
        
        # Should return None on error
        self.assertIsNone(result)


class TestAddForcedClosureLog(unittest.TestCase):
    """Test add_forced_closure_log function"""
    
    def setUp(self):
        """Reset state before each test"""
        state.bot_state.reconciliation_log = []
    
    def test_add_forced_closure_log_creates_entry(self):
        """Test that add_forced_closure_log creates a log entry"""
        details = {
            'side': 'LONG',
            'size': 0.01,
            'entry_price': 40000.0,
            'mark_price': 41000.0,
            'pnl': 10.0
        }
        
        state.add_forced_closure_log('BTC/USDT', 'tp_breach', details)
        
        self.assertEqual(len(state.bot_state.reconciliation_log), 1)
        
        log_entry = state.bot_state.reconciliation_log[0]
        self.assertEqual(log_entry['action'], 'forced_closure')
        self.assertEqual(log_entry['symbol'], 'BTC/USDT')
        self.assertEqual(log_entry['reason'], 'tp_breach')
        self.assertEqual(log_entry['details'], details)
        self.assertIn('timestamp', log_entry)
    
    def test_forced_closure_log_maintains_size_limit(self):
        """Test that log maintains size limit of 50 entries"""
        # Add 60 entries
        for i in range(60):
            state.add_forced_closure_log(f'SYMBOL{i}', 'test', {'test': i})
        
        # Should keep only last 50
        self.assertEqual(len(state.bot_state.reconciliation_log), 50)
        
        # Most recent should be first
        self.assertEqual(state.bot_state.reconciliation_log[0]['symbol'], 'SYMBOL59')


if __name__ == '__main__':
    unittest.main()
