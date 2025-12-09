import config

def get_trading_pairs():
    """
    Returns the fixed list of trading pairs from config.
    """
    return config.TRADING_PAIRS

if __name__ == "__main__":
    print("Trading pairs:", get_trading_pairs())
