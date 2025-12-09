import pandas as pd
import lux_algo

# Create dummy data
# Create larger dummy data to satisfy rolling window (period = length*10)
# We need at least 20+ points if length=2.
# Let's generate a sine wave or recognizable pattern.
import numpy as np
timestamps = pd.date_range(start='2024-01-01', periods=100, freq='30min')
closes = 100 + 10 * np.sin(np.linspace(0, 3*np.pi, 100))
highs = closes + 1
lows = closes - 1
opens = closes # simplified

df = pd.DataFrame({
    'timestamp': timestamps,
    'open': opens,
    'high': highs,
    'low': lows,
    'close': closes,
    'volume': [1000]*100
})
df.set_index('timestamp', inplace=True)

# Add a specific drop spike to trigger Bullish OB
# Index 50: Low drops significantly below recent range
df.iloc[50, df.columns.get_loc('low')] = df['low'].iloc[40:50].min() - 5
# Ensure it's a pivot: neighbors higher
df.iloc[49, df.columns.get_loc('low')] = df.iloc[50]['low'] + 2
df.iloc[51, df.columns.get_loc('low')] = df.iloc[50]['low'] + 2

# GAP UP after index 50 to avoid mitigation
# OB Top is High[50]. Let's say High[50] is Low[50]+1.
# We need Low[51+] > High[50].
ob_top = df.iloc[50]['high']
# Force subsequent lows to be strictly above ob_top
df.iloc[51:, df.columns.get_loc('low')] = ob_top + 2
df.iloc[51:, df.columns.get_loc('high')] = ob_top + 5
df.iloc[51:, df.columns.get_loc('close')] = ob_top + 3
df.iloc[51:, df.columns.get_loc('open')] = ob_top + 3

# DEBUG: Print data around spike
print("\nCheck Spike Data:")
print(df.iloc[45:55][['low', 'high', 'close']])

# Test OB Detection
# We need enough data for lookback. length=2 for testing with small data
print("Testing OB Detection with small length=2...")
obs = lux_algo.detect_order_blocks(df, length=2)

# DEBUG: Check bands
print("\nLower Band at 50:")
# period = 2 * 10 = 20
# lower_band[50] = min(low[30:50])
print(df['low'].rolling(20).min().shift(1).iloc[50])


print(f"Found {len(obs)} Order Blocks.")
for ob in obs:
    print(ob)

# Test Mitigation
# If we add a candle that hits the OB
print("\nTesting Mitigation Logic...")
# Manually add an OB
test_ob = {
    'type': 'bullish',
    'ob_top': 100,
    'ob_bottom': 99,
    'confirm_index': 5
}
# Data that does NOT touch 100
df_safe = pd.DataFrame({'low': [101, 102, 103], 'high': [105, 106, 107]})
# Data that touches 100
df_hit = pd.DataFrame({'low': [101, 99.5, 103], 'high': [105, 100, 107]})

from lux_algo import detect_order_blocks # actually we need to test check_mitigation logic inside detect
# Since logic is embedded, let's trust the unit test of logic if we can run it.
# Or I can just check if my previous run found anything.
