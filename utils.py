import config
import logging

logger = logging.getLogger(__name__)

# Supported TP/SL order types (including limit variants)
TP_SL_ORDER_TYPES = {
    'STOP', 'STOP_MARKET', 'STOP_LIMIT',
    'TAKE_PROFIT', 'TAKE_PROFIT_MARKET', 'TAKE_PROFIT_LIMIT'
}


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
    Normalize a trading symbol to a consistent format for comparison.
    
    Handles various symbol formats like:
    - "BTC/USDC:USDC" -> "BTC/USDC" (strip settlement suffix)
    - "BTC/USDC" -> "BTC/USDC" 
    - "BTCUSDC" -> "BTCUSDC"
    
    This is used for comparing symbols from different sources (exchange, position,
    orders) which may use different formats. For example, Hyperliquid may return
    orders with symbol "BTC/USDC" while the position uses "BTC/USDC:USDC".
    
    Args:
        symbol: Input symbol string
        
    Returns:
        str: Normalized symbol string for comparison purposes
    """
    if not symbol:
        return symbol
    
    resolved = symbol.strip()
    
    # Strip settlement currency suffix (e.g., ":USDC" from "BTC/USDC:USDC")
    # This allows matching between "BTC/USDC:USDC" and "BTC/USDC"
    if ':' in resolved:
        resolved = resolved.split(':')[0]
    
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
