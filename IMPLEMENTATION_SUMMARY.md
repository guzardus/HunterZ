# TP/SL Management Implementation Summary

## Overview
This implementation ensures all open positions have proper Take-Profit (TP) and Stop-Loss (SL) orders attached, addressing the issue where positions appeared in Binance UI without TP/SL indicators.

## Problem Addressed
- Users saw open positions without TP/SL attached in Binance UI ("TP/SL for position" shows --/--)
- TP/SL orders were not reliably present after entry orders filled
- No mechanism to repair missing or mismatched TP/SL orders

## Solution Components

### 1. Position Reconciliation (`main.py`)

#### `reconcile_position_tp_sl(client, symbol, position, pending_order)`
- Checks if a position has corresponding TP/SL orders on the exchange
- Detects missing SL or TP orders and places them
- Detects quantity mismatches (tolerance: 1%) and cancels/replaces orders
- Uses pending order data if available, otherwise calculates TP/SL from position
- Logs all actions to reconciliation log

#### `reconcile_all_positions_tp_sl(client)`
- Fetches all open positions from exchange
- Runs `reconcile_position_tp_sl()` for each position
- Called at startup and every 10 minutes
- Provides summary of reconciliation results

### 2. TP/SL Derivation from Orders (`state.py`)

#### `_normalize_order_field(order, field_name, fallback_name)`
- Helper function to handle field name variations (camelCase vs snake_case)
- Ensures compatibility with different exchange formats

#### `compute_position_tp_sl(symbol, exchange_open_orders)`
- Scans exchange orders for STOP_MARKET and TAKE_PROFIT_MARKET orders
- Extracts stop prices for the specified symbol
- Returns dict with take_profit and stop_loss values

#### `enrich_positions_with_tp_sl()`
- Updates all positions in state with TP/SL derived from exchange orders
- Called after fetching exchange orders in main loop
- Ensures frontend displays accurate TP/SL information

### 3. Exchange Client Enhancements (`execution.py`)

#### `get_tp_sl_orders_for_position(symbol)`
- Retrieves existing TP/SL orders for a symbol
- Identifies orders by type (STOP_MARKET, TAKE_PROFIT_MARKET)
- Returns dict with sl_order and tp_order

#### `cancel_order(symbol, order_id)`
- Cancels a specific order by ID
- Used for removing mismatched TP/SL orders before replacement

### 4. Configuration (`config.py`)

New constants for maintainability:
- `TP_SL_QUANTITY_TOLERANCE = 0.01` (1% tolerance for quantity matching)
- `POSITION_RECONCILIATION_INTERVAL = 600` (10 minutes in seconds)

## Flow Diagrams

### Startup Flow
```
1. Initialize state (load pending orders from disk)
2. Reconcile live orders (match with strategy)
3. Reconcile all positions TP/SL ← NEW
   - For each open position:
     - Check for TP/SL orders
     - Place missing orders
     - Fix quantity mismatches
4. Start main bot loop
```

### Main Loop Flow
```
1. Check for periodic reconciliation (every 10 min) ← NEW
2. Process pending orders (check fills)
3. Fetch balance and exchange orders
4. Enrich positions with TP/SL ← NEW
5. For each trading pair:
   - Update position
   - Fetch OHLCV
   - Detect order blocks
   - Place new limit orders if needed
6. Sleep 2 minutes
```

### Entry Fill Flow
```
1. Detect limit order filled
2. Format TP/SL prices with precision
3. Place STOP_MARKET order (SL)
4. Place TAKE_PROFIT_MARKET order (TP)
5. Record trade with TP/SL info
6. Remove from pending orders
```

## Testing

### Test Coverage (13 tests, all passing)

#### Unit Tests (`test_tp_sl_reconciliation.py`)
- TP/SL derivation with both orders present
- TP/SL derivation with only SL
- TP/SL derivation with only TP
- TP/SL derivation with no orders
- TP/SL derivation filtering by symbol
- Position enrichment (single position)
- Position enrichment (multiple positions)

#### Integration Tests (`test_execution_flow.py`)
- Place TP/SL for LONG position
- Place TP/SL for SHORT position
- Retrieve TP/SL orders for position
- Detect missing SL order
- Detect missing TP order
- Cancel and replace on quantity mismatch

### Running Tests
```bash
cd /path/to/HunterZ
python tests/run_tests.py -v
```

## Manual Testing Scenarios

### Scenario 1: Missing TP/SL Repair
1. Start bot on testnet
2. Wait for entry to fill
3. Manually cancel SL or TP order in Binance UI
4. Wait up to 10 minutes or restart bot
5. **Expected**: Missing order is recreated

### Scenario 2: Quantity Mismatch Repair
1. Open a position with TP/SL
2. Manually change TP or SL quantity in Binance UI
3. Restart bot or wait for reconciliation
4. **Expected**: Old orders cancelled, new ones placed with correct size

### Scenario 3: Restart with Open Position
1. Stop bot with open position
2. Restart bot
3. **Expected**: Position reconciliation runs at startup, TP/SL verified/repaired

## API Changes

### Position Data Structure
Positions now include derived TP/SL:
```json
{
  "symbol": "BTC/USDT",
  "side": "LONG",
  "size": 0.1,
  "entry_price": 45000.0,
  "mark_price": 46000.0,
  "unrealized_pnl": 100.0,
  "leverage": 10,
  "take_profit": 49000.0,  // Derived from exchange orders
  "stop_loss": 43000.0      // Derived from exchange orders
}
```

### Reconciliation Log
New entries in `/api/metrics`:
- `missing_sl_detected`
- `missing_tp_detected`
- `sl_quantity_mismatch`
- `tp_quantity_mismatch`
- `sl_placed`
- `tp_placed`
- `tp_sl_placed`
- `position_reconciliation_start`
- `position_reconciliation_complete`

## Benefits

1. **Reliability**: All positions have proper risk management
2. **Accuracy**: TP/SL displayed in UI matches exchange reality
3. **Automation**: No manual intervention needed
4. **Recovery**: Repairs missing or incorrect orders automatically
5. **Visibility**: Comprehensive logging for debugging
6. **Testing**: Full test coverage ensures correctness

## Files Changed

- `execution.py`: Added TP/SL retrieval and order cancellation
- `state.py`: Added TP/SL derivation and position enrichment
- `main.py`: Added position reconciliation logic
- `config.py`: Added reconciliation constants
- `README.md`: Updated documentation
- `tests/`: New test suite with 13 tests

## Configuration Options

In `config.py`:
```python
# Adjust tolerance for quantity matching (default 1%)
TP_SL_QUANTITY_TOLERANCE = 0.01

# Adjust reconciliation frequency (default 10 minutes)
POSITION_RECONCILIATION_INTERVAL = 600
```

## Known Limitations

1. TP/SL calculation for reconciliation uses simple percentage-based fallback if no pending order data exists
2. Reconciliation runs every 10 minutes (configurable), not continuously
3. Assumes Binance Futures API format (STOP_MARKET, TAKE_PROFIT_MARKET)

## Future Enhancements

1. Real-time WebSocket monitoring for instant detection of missing TP/SL
2. Configurable reconciliation strategies (percentage-based, fixed, ATR-based)
3. Multi-exchange support with format adapters
4. Alerting system for reconciliation failures
5. Dashboard widget showing reconciliation status

## Security

- No security vulnerabilities detected by CodeQL
- All external inputs validated
- Proper error handling prevents crashes
- Logging doesn't expose sensitive data

## Deployment Checklist

- [x] All tests passing
- [x] Documentation updated
- [x] Security scan clean
- [x] Code review feedback addressed
- [x] Configuration constants extracted
- [x] Field name normalization implemented
- [ ] Manual testing on testnet (optional)
- [ ] Deploy to production (user action)

## Support

For issues or questions:
1. Check console logs for reconciliation messages
2. Review reconciliation log in UI (`/api/metrics`)
3. Run automated tests: `python tests/run_tests.py`
4. Enable verbose logging if needed

---
**Implementation Date**: December 2025
**Test Coverage**: 13 tests, 100% passing
**Security Status**: No vulnerabilities detected
