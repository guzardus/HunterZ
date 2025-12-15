# Metrics Fix Verification Checklist

Use this checklist to verify all metrics issues have been resolved.

## Before You Start
1. Ensure you have the latest code from the `copilot/fix-front-end-metrics` branch
2. Make sure your `.env` file is configured with valid API credentials
3. Start the bot: `python main.py` or `python api.py` (for web UI)

## Verification Steps

### ✅ Step 1: Check Startup Logs
When the bot starts, you should see these messages:
```
Initializing bot state...
Loaded X pending orders from disk
Loaded metrics from disk: {...}
Loaded X trades from disk, total P&L: Y.YY
=== Starting Order Reconciliation ===
=== Starting Position TP/SL Reconciliation ===
=== Reconciling Existing Positions with Trade History ===
```

**Expected Result:** ✅ All initialization messages appear without errors

---

### ✅ Step 2: Active Positions Count
**Location:** Dashboard header - "ACTIVE POSITIONS" metric

**Before Fix:** Shows 0 even with open positions
**After Fix:** Shows correct count of open positions

**Test:**
1. Open the web UI at `http://localhost:8000`
2. Look at the "ACTIVE POSITIONS" metric in the "WALLET & ACCOUNT" section
3. Count should match your actual open positions on Binance

**Expected Result:** ✅ Count matches actual open positions (e.g., 3)

---

### ✅ Step 3: Active Positions Table
**Location:** "ACTIVE POSITIONS" section (table below metrics)

**Before Fix:** Shows "No active positions" even with open positions
**After Fix:** Shows all open positions with details

**Test:**
1. Scroll to the "ACTIVE POSITIONS" table
2. Verify you see rows for each open position
3. Check each row has these columns:
   - Symbol (e.g., BTC/USDT)
   - Side (LONG/SHORT in green/red)
   - Size (e.g., 0.1000)
   - Entry Price (e.g., $45,000.00)
   - Mark Price (e.g., $45,500.00)
   - Unrealized P&L (in green/red, e.g., 50.00 USDT)
   - Leverage (e.g., 10x)
   - **Duration** (e.g., "2h 15m" or "1d 5h") ⭐ NEW
   - Take Profit (e.g., $49,000.00)
   - Stop Loss (e.g., $43,000.00)

**Expected Result:** ✅ All positions displayed with duration column

---

### ✅ Step 4: Pending Orders Count
**Location:** Dashboard metrics - "PENDING ORDERS"

**Before Fix:** Inaccurate count (showed 9)
**After Fix:** Accurate count from bot's pending orders state

**Test:**
1. Check the "PENDING ORDERS" metric
2. Compare with actual pending orders in the "PENDING ORDERS" table below
3. Count should match bot-tracked pending orders (waiting for TP/SL placement)

**Expected Result:** ✅ Count is accurate

---

### ✅ Step 5: Exchange Orders Count
**Location:** Dashboard metrics - "EXCHANGE ORDERS"

**Before Fix:** Shows 0
**After Fix:** Shows actual count from exchange

**Test:**
1. Check the "EXCHANGE ORDERS" metric
2. Count should reflect all open orders on the exchange (including TP/SL orders)
3. Check Binance to verify the count

**Expected Result:** ✅ Count matches actual exchange orders

---

### ✅ Step 6: Order Metrics (Placed, Cancelled, Filled)
**Location:** Dashboard metrics

**Before Fix:** Incorrect counts, resets on restart
**After Fix:** Accurate cumulative counts, persisted across restarts

**Test 1 - Initial Values:**
1. Note the current values:
   - PLACED (e.g., 74)
   - CANCELLED (e.g., 1)
   - FILLED (e.g., 8)

**Test 2 - Persistence:**
1. Stop the bot
2. Restart the bot
3. Check that the values are preserved

**Expected Result:** ✅ Values persist across restarts

---

### ✅ Step 7: Total P&L
**Location:** Dashboard metrics - "TOTAL P&L"

**Before Fix:** Shows 0.00
**After Fix:** Shows sum of all closed trade P&L

**Test:**
1. Check the "TOTAL P&L" metric
2. Value should be sum of all closed trades in trade history
3. Color: Green if positive, red if negative

**Expected Result:** ✅ Shows calculated P&L from trade history

---

### ✅ Step 8: Win Rate
**Location:** Dashboard metrics - "WIN RATE"

**Before Fix:** Shows 0%
**After Fix:** Shows percentage of winning trades

**Test:**
1. Check the "WIN RATE" metric
2. Formula: (winning trades / total closed trades) × 100
3. Color: Green if ≥50%, red if <50%

**Expected Result:** ✅ Shows calculated win rate from closed trades

---

### ✅ Step 9: Pending Orders Table
**Location:** "PENDING ORDERS" section

**Test:**
1. Check the "PENDING ORDERS" table
2. Should show rows with:
   - Symbol
   - Side (with type indicator like "(TP)", "(SL)", etc.)
   - Entry Price
   - Size
   - Take Profit
   - Stop Loss
   - Order ID (truncated)
   - Time Placed
3. Orders highlighted in light green are from exchange

**Expected Result:** ✅ All pending orders displayed with accurate details

---

### ✅ Step 10: Trade History
**Location:** "TRADE HISTORY" section

**Before Fix:** Shows "No trades yet"
**After Fix:** Shows all closed trades

**Test:**
1. Check the "TRADE HISTORY" table
2. Should show rows with:
   - Time (Melbourne timezone)
   - Symbol
   - Side (LONG/SHORT)
   - Entry Price
   - Exit Price
   - Size
   - P&L (in green/red)
   - P&L %
   - Duration
   - Status (CLOSED)
3. Most recent trades appear first

**Expected Result:** ✅ Trade history populated with closed trades

---

### ✅ Step 11: Data Files Created
**Location:** `data/` directory

**Test:**
```bash
ls -la data/
cat data/metrics.json
cat data/trade_history.json
cat data/pending_orders.json
```

**Expected Files:**
1. `data/metrics.json` - Contains order metrics
2. `data/trade_history.json` - Contains trade history
3. `data/pending_orders.json` - Contains pending orders

**Expected Result:** ✅ All files exist and contain valid JSON

---

### ✅ Step 12: Restart Persistence Test
**Test:**
1. Note all current metric values
2. Note all positions and trades
3. Stop the bot completely
4. Restart the bot
5. Verify all values are restored

**Expected Result:** ✅ All data persisted across restart

---

## API Endpoint Tests

### Test API Endpoints Directly
```bash
# Get positions
curl http://localhost:8000/api/positions | jq

# Get trades
curl http://localhost:8000/api/trades | jq

# Get metrics
curl http://localhost:8000/api/metrics | jq

# Get status
curl http://localhost:8000/api/status | jq
```

**Expected Result:** ✅ All endpoints return valid JSON with data

---

## Common Issues & Solutions

### Issue: Positions show but duration is "-"
**Cause:** Position existed before fix, no entry_time recorded
**Solution:** Close and reopen position, or wait for next entry

### Issue: Metrics still show 0 after restart
**Cause:** Bot hasn't placed/cancelled/filled any orders yet
**Solution:** Metrics will update as orders are processed

### Issue: Trade history empty
**Cause:** No trades have been closed yet
**Solution:** Trade history populates when positions close

### Issue: Data files missing
**Cause:** Bot hasn't run long enough to create files
**Solution:** Wait for bot to process at least one order/trade

---

## Success Criteria

All items below should be ✅:

- [ ] Active positions count correct
- [ ] Active positions table shows all positions
- [ ] Duration column displays elapsed time
- [ ] Pending orders count accurate
- [ ] Exchange orders count accurate
- [ ] Placed orders metric persists
- [ ] Cancelled orders metric persists
- [ ] Filled orders metric persists
- [ ] Total P&L calculated correctly
- [ ] Win rate calculated correctly
- [ ] Trade history populated
- [ ] All data files created
- [ ] Metrics persist after restart
- [ ] No errors in console logs

---

## Need Help?

If any verification step fails:
1. Check the bot logs for errors
2. Verify your API credentials are correct
3. Check that you're using testnet if testing
4. Review `METRICS_FIX_SUMMARY.md` for detailed information
5. Check data files for corruption: `cat data/*.json`

---

**Last Updated:** 2024-12-15
**Branch:** copilot/fix-front-end-metrics
