import logging
from order_utils import log_tp_sl_inconsistent_throttled

logger = logging.getLogger(__name__)


def get_position_side(pos: dict) -> str:
    """
    Determine canonical position side string: 'LONG' or 'SHORT'.
    Args:
        pos: position-like mapping that may include keys such as side, positionSide,
             position_side, size, amount, positionAmt, or qty.

    Behavior:
        - Uses explicit side fields first when they resolve to LONG/SHORT (case-insensitive).
        - Falls back to numeric size sign (positive -> LONG, negative -> SHORT, zero -> LONG default).
    """
    # Try explicit fields
    for key in ("side", "positionSide", "position_side"):
        if key in pos and pos[key] is not None:
            try:
                side = str(pos[key]).upper()
                if side in ("LONG", "SHORT"):
                    return side
            except (TypeError, ValueError, AttributeError):
                pass

    # Fall back to numeric size sign
    for key in ("size", "amount", "positionAmt", "qty"):
        if key in pos and pos[key] is not None:
            try:
                val = float(pos[key])
                if val > 0:
                    return "LONG"
                if val < 0:
                    return "SHORT"
            except (TypeError, ValueError, AttributeError):
                pass

    # Default
    return "LONG"


def log_tp_sl_inconsistent(
    pos: dict, entry: float | int, tp: float | int | None, sl: float | int | None
) -> None:
    """
    Logs a consistent, correctly-sided warning message about TP/SL inconsistency.
    Use this to replace any hard-coded or incorrectly sided log messages.
    
    Uses throttled logging to avoid spam - at most once per minute per symbol.

    Args:
        pos: position-like mapping containing symbol/side/size fields.
        entry: entry price for the position.
        tp: configured take-profit price.
        sl: configured stop-loss price.
    """
    symbol = pos.get("symbol") or pos.get("market") or "UNKNOWN"
    position_side = get_position_side(pos)
    
    # Use throttled logging to avoid repeated spam
    log_tp_sl_inconsistent_throttled(symbol, position_side, entry, tp, sl)
