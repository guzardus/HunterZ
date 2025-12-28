import logging

logger = logging.getLogger(__name__)


def get_position_side(pos: dict) -> str:
    """
    Determine canonical position side string: 'LONG' or 'SHORT'.
    Tries explicit fields first (side, positionSide, position_side).
    Falls back to numeric size sign (positive -> LONG, negative -> SHORT).
    """
    # Try explicit fields
    for key in ("side", "positionSide", "position_side"):
        if key in pos and pos[key] is not None:
            try:
                side = str(pos[key]).upper()
                if side in ("LONG", "SHORT"):
                    return side
            except Exception:
                pass

    # Fall back to numeric size sign
    for key in ("size", "amount", "positionAmt", "qty"):
        if key in pos and pos[key] is not None:
            try:
                val = float(pos[key])
                return "LONG" if val > 0 else "SHORT"
            except Exception:
                pass

    # Default
    return "LONG"


def log_tp_sl_inconsistent(pos: dict, entry, tp, sl):
    """
    Logs a consistent, correctly-sided warning message about TP/SL inconsistency.
    Use this to replace any hard-coded or incorrectly sided log messages.
    """
    symbol = pos.get("symbol") or pos.get("market") or "UNKNOWN"
    position_side = get_position_side(pos)
    logger.warning(
        "⚠️ Skipping closure for %s: TP/SL inconsistent for %s (entry %s, TP %s, SL %s)",
        symbol,
        position_side,
        entry,
        tp,
        sl,
    )
