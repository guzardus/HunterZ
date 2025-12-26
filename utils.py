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


def normalize_symbol(symbol):
    """
    Normalize a trading symbol to a consistent format.
    
    Handles various symbol formats like:
    - "BTC/USDC:USDC" -> "BTC/USDC:USDC" (already normalized for Hyperliquid)
    - "BTC/USDC" -> "BTC/USDC"
    - "BTCUSDC" -> "BTCUSDC"
    
    Args:
        symbol: Input symbol string
        
    Returns:
        str: Normalized symbol string
    """
    if not symbol:
        return symbol
    
    resolved = symbol.strip()
    
    # Log the normalization for debugging
    logger.debug("normalize_symbol: input=%s -> resolved=%s", symbol, resolved)
    
    return resolved


def get_trading_pairs():
    """
    Returns the fixed list of trading pairs from config.
    """
    return config.TRADING_PAIRS

if __name__ == "__main__":
    print("Trading pairs:", get_trading_pairs())
