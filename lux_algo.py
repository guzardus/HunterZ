import pandas as pd
import numpy as np

def detect_order_blocks(df, length=5):
    """
    Detects Bullish and Bearish Order Blocks based on LuxAlgo strategy.
    
    Args:
        df (pd.DataFrame): Dataframe with 'open', 'high', 'low', 'close', 'volume' columns.
        length (int): Lookback/Lookforward length for pivots.
        
    Returns:
        list: List of valid, unmitigated Order Blocks.
    """
    obs = []
    
    # Calculate Rolling Max/Min for Bands (Using length*2 as proxy for "period")
    # Note: User didn't specify band length, assuming similar scale to pivot
    period = length * 10 # 50 period
    df['upper_band'] = df['high'].rolling(window=period).max().shift(1)
    df['lower_band'] = df['low'].rolling(window=period).min().shift(1)
    
    # Identify Pivots
    # Pivot High: High[i] > High[i +/- 1...length]
    # Pivot Low: Low[i] < Low[i +/- 1...length]
    # We must account for look-ahead bias by only confirming at i+length
    
    # We'll iterate through the DF up to len - length
    # Valid index range for pivot check: [length, len(df) - length]
    
    for i in range(length, len(df) - length):
        # We are at time 'i'. But we can only confirm this pivot at time 'i + length'.
        # For live trading, we only care if we have CONFIRMED it by "now" (last candle).
        # So 'i' is the potential pivot candle. 'i+length' is the confirm candle.
        
        # Check Pivot Low (Bullish OB Setup?)
        # User Logic: Volume Pivot High + Market Structure condition (Low[length] < Lower Band)
        # Assuming "Volume Pivot Low" for Bullish.
        # Check if Low[i] is minimum in window [i-length, i+length]
        window_lows = df['low'].iloc[i-length : i+length+1]
        is_pivot_low = df['low'].iloc[i] == window_lows.min()
        
        if is_pivot_low:
            # Check market structure condition
            # "Low[length] < Lower Band".
            # Here 'Low[i]' is the current low. 'Lower Band' at i.
            if df['low'].iloc[i] < df['lower_band'].iloc[i]:
                # Found Potential Bullish OB
                ob = {
                    'type': 'bullish',
                    'top': df['high'].iloc[i], # Entry at top of candle
                    'bottom': df['low'].iloc[i] - (df['high'].iloc[i] - df['low'].iloc[i])*0.1, # SL slightly below
                    # User said: "Entry Price: Top edge... Stop Loss: Minimally below bottom edge"
                    # Let's refine SL later in risk manager, just store raw OB limits here.
                    'ob_top': df['high'].iloc[i],
                    'ob_bottom': df['low'].iloc[i],
                    'time': df.index[i],
                    'confirm_index': i + length
                }
                obs.append(ob)
                
        # Check Pivot High (Bearish OB Setup)
        window_highs = df['high'].iloc[i-length : i+length+1]
        is_pivot_high = df['high'].iloc[i] == window_highs.max()
        
        if is_pivot_high:
            if df['high'].iloc[i] > df['upper_band'].iloc[i]:
                # Found Potential Bearish OB
                ob = {
                    'type': 'bearish',
                    'top': df['high'].iloc[i], # SL above top
                    'bottom': df['low'].iloc[i], # Entry at bottom
                    'ob_top': df['high'].iloc[i],
                    'ob_bottom': df['low'].iloc[i],
                    'time': df.index[i],
                    'confirm_index': i + length
                }
                obs.append(ob)
                
    # Now Check Mitigation
    # Iterate through confirmed OBs and check if price touched them AFTER confirmation
    valid_obs = []
    for ob in obs:
        # Check price action from confirm_index + 1 to end
        start_check = ob['confirm_index'] + 1
        if start_check >= len(df):
            # Not confirmed yet or just confirmed
            valid_obs.append(ob)
            continue
            
        mitigated = False
        subset = df.iloc[start_check:]
        
        if ob['type'] == 'bullish':
            # Mitigated if Price drops into the zone (Top to Bottom)
            # Or wicks into it.
            # Entry is at 'ob_top'.
            # If Low of any subsequent candle <= ob_top, it triggered/mitigated.
            if (subset['low'] <= ob['ob_top']).any():
                mitigated = True
                
        elif ob['type'] == 'bearish':
            # Mitigated if Price rises into the zone (Bottom to Top)
            # Entry is at 'ob_bottom'.
            # If High of any subsequent candle >= ob_bottom, it triggered/mitigated.
            if (subset['high'] >= ob['ob_bottom']).any():
                mitigated = True
                
        if not mitigated:
            valid_obs.append(ob)
            
    return valid_obs
