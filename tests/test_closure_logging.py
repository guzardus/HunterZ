import logging

import pytest

from reconciler.closure_fix import log_tp_sl_inconsistent


def test_log_includes_long_side(caplog):
    caplog.set_level(logging.WARNING)
    pos = {"symbol": "SOL/USDT:USDT", "side": "LONG", "size": 1}
    log_tp_sl_inconsistent(pos, entry=124.28, tp=126.77, sl=123.04)
    assert any("TP/SL inconsistent for LONG" in r.getMessage() for r in caplog.records), (
        "Expected log to contain 'TP/SL inconsistent for LONG'"
    )


def test_log_includes_short_side_from_negative_size(caplog):
    caplog.set_level(logging.WARNING)
    pos = {"symbol": "X/USDT", "size": -2}  # negative size -> SHORT
    log_tp_sl_inconsistent(pos, entry=100, tp=90, sl=105)
    assert any("TP/SL inconsistent for SHORT" in r.getMessage() for r in caplog.records), (
        "Expected log to contain 'TP/SL inconsistent for SHORT'"
    )
