import time
import pandas as pd
import config
import utils
import lux_algo
import risk_manager
import state
from execution import BinanceClient
import threading

def prepare_dataframe(ohlcv):
    """Converts CCXT OHLCV list to DataFrame."""
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    return df

def run_bot_logic():
    print("Starting LuxAlgo Order Block Bot Logic...")
    client = BinanceClient()
    
    while True:
        try:
            # 1. Fetch Trading Pairs
            symbols = utils.get_trading_pairs()
            # print(f"\nScanning {len(symbols)} pairs: {symbols}")
            
            balance = client.get_balance()
            state.update_balance(balance)
            # print(f"Current Balance: {balance:.2f} USDT")
            
            for symbol in symbols:
                # print(f"\n--- Processing {symbol} ---")
                
                # Check current position
                position = client.get_position(symbol)
                state.update_position(symbol, position)
                
                # 2. Fetch Data
                ohlcv = client.fetch_ohlcv(symbol)
                if not ohlcv:
                    continue
                    
                df = prepare_dataframe(ohlcv)
                
                # Update State for Frontend Chart
                state.update_ohlcv(symbol, df)
                
                # 3. Detect Order Blocks
                obs = lux_algo.detect_order_blocks(df)
                
                # Update State for Frontend OBs
                # We want to serialize OBs for the frontend
                # Convert timestamps to ISO string or Unix ms
                serializable_obs = []
                for ob in obs:
                    ob_copy = ob.copy()
                    ob_copy['time'] = int(ob['time'].timestamp()) # Unix
                    # confirm_index is internal, maybe not needed for frontend
                    serializable_obs.append(ob_copy)
                state.update_order_blocks(symbol, serializable_obs)

                if not obs:
                    # print("No valid unmitigated order blocks found.")
                    continue
                
                has_position = position and float(position['entryPrice']) > 0 and float(position['positionAmt']) != 0
                if has_position:
                    # print(f"Position exists for {symbol}. Skipping new entry search.")
                    continue
                    
                # 4. Select Best OB
                current_price = df['close'].iloc[-1]
                
                valid_candidates = []
                for ob in obs:
                    if ob['type'] == 'bullish' and current_price > ob['ob_top']:
                        dist = abs(current_price - ob['ob_top'])
                        ob['distance'] = dist
                        valid_candidates.append(ob)
                    elif ob['type'] == 'bearish' and current_price < ob['ob_bottom']:
                        dist = abs(current_price - ob['ob_bottom'])
                        ob['distance'] = dist
                        valid_candidates.append(ob)
                        
                if not valid_candidates:
                    continue
                    
                # Sort by distance
                valid_candidates.sort(key=lambda x: x['distance'])
                best_ob = valid_candidates[0]
                
                # print(f"Found Candidate OB: {best_ob['type'].upper()} at {best_ob['ob_top']}-{best_ob['ob_bottom']}")
                
                # 5. Calculate Parameters
                params = risk_manager.calculate_trade_params(best_ob, balance)
                if not params:
                    continue
                params['symbol'] = symbol
                
                # 6. Execute
                client.cancel_all_orders(symbol)
                
                qty = client.exchange.amount_to_precision(symbol, params['quantity'])
                price = client.exchange.price_to_precision(symbol, params['entry_price'])
                
                print(f"Placing Order: {params['side']} {qty} @ {price}")
                order = client.place_limit_order(symbol, params['side'], qty, price)
                
                # if order:
                #     print(f"Order Placed ID: {order['id']}")
            
            # Decrease sleep time for more responsive UI updates? 
            # Or keep it, as 30m candles don't change fast.
            # But recent price update is nice.
            time.sleep(60) # updates every 1 min
            
        except Exception as e:
            print(f"Top-level error: {e}")
            time.sleep(60)

def start_bot_thread():
    t = threading.Thread(target=run_bot_logic, daemon=True)
    t.start()
    return t

if __name__ == "__main__":
    run_bot_logic()
