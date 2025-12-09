import utils
import config

print("Testing Top 6 Symbol Fetcher...")
symbols = utils.get_top_symbols(limit=config.TOP_N_COINS)
print(f"Fetched {len(symbols)} symbols: {symbols}")

print("\nChecking against Blacklist...")
blacklist_hit = False
for s in symbols:
    if s in config.BLACKLIST:
        print(f"FAIL: Found blacklisted symbol {s}")
        blacklist_hit = True

if not blacklist_hit:
    print("PASS: No stablecoins found.")
else:
    print("FAIL: Stablecoins detected.")
