import config

def calculate_trade_params(ob, balance, current_price=None):
    """
    Calculates entry, stop loss, take profit, and quantity for a trade.
    
    Args:
        ob (dict): The Order Block dictionary.
        balance (float): Account balance in USDT.
        current_price (float, optional): Current price (for verification or nearest check).
        
    Returns:
        dict: Trade parameters (entry, sl, tp, quantity, side).
    """
    risk_amount = balance * (config.RISK_PER_TRADE / 100.0)
    
    entry_price = 0.0
    stop_loss = 0.0
    take_profit = 0.0
    side = ''
    
    # Buffer for SL (0.1%)
    sl_buffer = 0.001 
    
    if ob['type'] == 'bullish':
        side = 'buy'
        entry_price = ob['ob_top']
        # SL below bottom
        stop_loss = ob['ob_bottom'] * (1 - sl_buffer)
        
        # Risk per unit = Entry - SL
        risk_per_unit = entry_price - stop_loss
        
        if risk_per_unit <= 0:
            print(f"Invalid Trade Parameters (Bullish): Entry {entry_price} <= SL {stop_loss}")
            return None
            
        # TP = Entry + (Risk * RR)
        take_profit = entry_price + (risk_per_unit * config.RR_RATIO)
        
    elif ob['type'] == 'bearish':
        side = 'sell'
        entry_price = ob['ob_bottom']
        # SL above top
        stop_loss = ob['ob_top'] * (1 + sl_buffer)
        
        # Risk per unit = SL - Entry
        risk_per_unit = stop_loss - entry_price
        
        if risk_per_unit <= 0:
            print(f"Invalid Trade Parameters (Bearish): SL {stop_loss} <= Entry {entry_price}")
            return None
            
        # TP = Entry - (Risk * RR)
        take_profit = entry_price - (risk_per_unit * config.RR_RATIO)
    
    # Calculate Quantity
    # Quantity = Risk Amount / Risk Per Unit
    quantity = risk_amount / risk_per_unit
    
    return {
        'symbol': '', # Filled by caller
        'side': side,
        'entry_price': entry_price,
        'stop_loss': stop_loss,
        'take_profit': take_profit,
        'quantity': quantity
    }


def compute_tp_sl(entry, tp_pct, sl_pct, side):
    """
    Compute take-profit and stop-loss levels based on side-specific logic.

    Args:
        entry (float): Entry price
        tp_pct (float): Take-profit percentage expressed as decimal (e.g., 0.02 for 2%)
        sl_pct (float): Stop-loss percentage expressed as decimal
        side (str): 'long' or 'short'

    Returns:
        tuple: (take_profit, stop_loss)
    """
    if tp_pct <= 0 or sl_pct <= 0:
        raise ValueError(f"tp_pct and sl_pct must be positive. Got tp_pct={tp_pct}, sl_pct={sl_pct}")
    s = side.lower()
    if s == 'long':
        tp = entry * (1 + tp_pct)
        sl = entry * (1 - sl_pct)
    elif s == 'short':
        tp = entry * (1 - tp_pct)
        sl = entry * (1 + sl_pct)
    else:
        raise ValueError("Invalid side: expected 'long' or 'short'")

    if s == 'long' and not (tp > entry and sl < entry):
        raise ValueError(f"TP/SL incorrect for {s.upper()}: tp={tp}, sl={sl}, entry={entry}")
    if s == 'short' and not (tp < entry and sl > entry):
        raise ValueError(f"TP/SL incorrect for {s.upper()}: tp={tp}, sl={sl}, entry={entry}")
    return tp, sl
