import config

def calculate_trade_params(ob, balance, current_price=None):
    """
    Calculates entry, stop loss, take profit, and quantity for a trade.
    
    Args:
        ob (dict): The Order Block dictionary.
        balance (float): Account balance in USDC.
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
