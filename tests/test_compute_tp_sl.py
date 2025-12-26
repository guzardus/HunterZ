import unittest

from risk_manager import compute_tp_sl


class ComputeTpSlTests(unittest.TestCase):
    def test_long_tp_sl(self):
        tp, sl = compute_tp_sl(100.0, 0.02, 0.01, 'long')
        self.assertAlmostEqual(tp, 102.0)
        self.assertAlmostEqual(sl, 99.0)

    def test_short_tp_sl(self):
        tp, sl = compute_tp_sl(100.0, 0.02, 0.01, 'short')
        self.assertAlmostEqual(tp, 98.0)
        self.assertAlmostEqual(sl, 101.0)

    def test_invalid_side(self):
        with self.assertRaises(ValueError):
            compute_tp_sl(100.0, 0.02, 0.01, 'invalid')


if __name__ == '__main__':
    unittest.main()
