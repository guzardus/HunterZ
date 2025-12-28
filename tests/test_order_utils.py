import unittest
from unittest.mock import MagicMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import order_utils
import state


class DummyExchange:
    def __init__(self, price):
        self.price = price
        self.markets = {"BTC/USDT": {"info": {"filters": [{"filterType": "PRICE_FILTER", "tickSize": "0.1"}]}}}

    def fetch_ticker(self, symbol):
        return {"last": self.price}

    def load_markets(self):
        return self.markets


class DummyClient:
    def __init__(self, price):
        self.exchange = DummyExchange(price)
        self.stop_calls = 0
        self.tp_calls = 0
        self.close_calls = 0

    def _resolve_symbol(self, symbol):
        return symbol

    def place_stop_loss(self, symbol, side, amount, stop_price):
        self.stop_calls += 1
        return {"id": "sl"}

    def place_take_profit(self, symbol, side, amount, tp_price):
        self.tp_calls += 1
        return {"id": "tp"}

    def close_position_market(self, symbol, side, amount, reason=""):
        self.close_calls += 1
        return {"id": "close"}


class TestOrderUtils(unittest.TestCase):
    def setUp(self):
        state.bot_state.tp_sl_backoff = {}

    def test_round_to_tick(self):
        self.assertEqual(order_utils.round_to_tick(123.456, 0.1), 123.5)
        self.assertEqual(order_utils.round_to_tick(0.00012345, 0.00001), 0.00012)

    def test_safe_place_tp_sl_places_conditionals(self):
        client = DummyClient(price=100)
        ok = order_utils.safe_place_tp_sl(client, "BTC/USDT", True, 1, 110, 90)
        self.assertTrue(ok)
        self.assertEqual(client.stop_calls, 1)
        self.assertEqual(client.tp_calls, 1)
        self.assertEqual(client.close_calls, 0)

    def test_safe_place_tp_sl_market_fallback_when_crossed(self):
        client = DummyClient(price=120)  # TP already crossed for long
        ok = order_utils.safe_place_tp_sl(client, "BTC/USDT", True, 1, 110, 90)
        self.assertTrue(ok)
        self.assertEqual(client.close_calls, 1)
        self.assertEqual(client.stop_calls, 0)
        self.assertEqual(client.tp_calls, 0)

    def test_backoff_skips_repeat_attempt(self):
        client = DummyClient(price=120)
        first = order_utils.safe_place_tp_sl(client, "BTC/USDT", True, 1, 110, 90)
        self.assertTrue(first)
        # second call should skip due to backoff
        second = order_utils.safe_place_tp_sl(client, "BTC/USDT", True, 1, 110, 90)
        self.assertFalse(second)
        self.assertEqual(client.close_calls, 1)


if __name__ == "__main__":
    unittest.main()
