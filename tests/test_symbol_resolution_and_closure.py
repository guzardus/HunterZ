import unittest

from execution import BinanceClient


class FakeExchange:
    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.markets = {
            'MATIC/USDT:USDT': {'symbol': 'MATIC/USDT:USDT', 'base': 'MATIC', 'quote': 'USDT'},
            'LTC/USDT:USDT': {'symbol': 'LTC/USDT:USDT', 'base': 'LTC', 'quote': 'USDT'},
        }
        self.last_order = None

    def load_markets(self):
        return self.markets

    def create_order(self, symbol, order_type, side, amount, price=None, params=None):
        if self.should_fail:
            raise Exception("reduceOnly rejected")
        self.last_order = {
            'symbol': symbol,
            'type': order_type,
            'side': side,
            'amount': amount,
            'price': price,
            'params': params,
        }
        return {'id': 'test', **self.last_order}


class SymbolResolutionAndClosureTests(unittest.TestCase):
    def setUp(self):
        self.client = BinanceClient.__new__(BinanceClient)
        self.client.exchange = FakeExchange()

    def test_resolve_symbol_uses_loaded_market_symbol(self):
        resolved = self.client._resolve_symbol('MATIC/USDT')
        self.assertEqual(resolved, 'MATIC/USDT:USDT')

    def test_close_position_market_uses_reduce_only_payload(self):
        order = self.client.close_position_market('LTC/USDT', 'buy', 1.5, 'tp_breach')
        self.assertIsNotNone(order)
        self.assertEqual(self.client.exchange.last_order['symbol'], 'LTC/USDT:USDT')
        self.assertEqual(self.client.exchange.last_order['type'], 'market')
        self.assertEqual(self.client.exchange.last_order['side'], 'buy')
        self.assertEqual(self.client.exchange.last_order['amount'], 1.5)
        self.assertEqual(self.client.exchange.last_order['price'], None)
        self.assertEqual(self.client.exchange.last_order['params'], {'reduceOnly': True})


if __name__ == '__main__':
    unittest.main()
