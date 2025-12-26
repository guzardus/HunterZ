import config
import logging

logger = logging.getLogger(__name__)


def safe_split(value, sep=':', maxsplit=-1):
    """
    Safely split value into parts. Returns [] if value is None or not str/castable.
    
    Args:
        value: The value to split
        sep: Separator string (default: ':')
        maxsplit: Maximum number of splits (-1 for unlimited)
        
    Returns:
        list: List of parts from the split, or empty list if value is None/invalid
    """
    if value is None:
        return []
    if not isinstance(value, str):
        try:
            value = str(value)
        except Exception:
            return []
    if maxsplit == -1:
        return value.split(sep)
    return value.split(sep, maxsplit)


def get_trading_pairs():
    """
    Returns the fixed list of trading pairs from config.
    """
    return config.TRADING_PAIRS

if __name__ == "__main__":
    print("Trading pairs:", get_trading_pairs())
