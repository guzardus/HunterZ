# Testing Guide for HunterZ Trading Bot

This document describes the testing infrastructure for the TP/SL management functionality.

## Test Structure

The tests are organized in the `tests/` directory:

```
tests/
├── __init__.py
├── run_tests.py                    # Test runner script
├── test_tp_sl_reconciliation.py    # Unit tests for TP/SL logic
└── test_execution_flow.py          # Integration tests with mocked exchange
```

## Running Tests

### Prerequisites

Install required dependencies:
```bash
pip install -r requirements.txt
```

### Run All Tests

```bash
# From the repository root
python tests/run_tests.py
```

### Run with Verbose Output

```bash
python tests/run_tests.py -v
```

### Run Specific Test Files

```bash
# Run only reconciliation tests
python tests/run_tests.py test_tp_sl_reconciliation

# Run only execution flow tests
python tests/run_tests.py test_execution_flow
```

### Using unittest directly

```bash
# From the repository root
python -m unittest discover tests -v
```

## Test Coverage

### Unit Tests (test_tp_sl_reconciliation.py)

These tests verify the logic for deriving TP/SL from exchange orders:

- `test_compute_position_tp_sl_with_both_orders`: Verify TP/SL extraction when both orders exist
- `test_compute_position_tp_sl_with_only_sl`: Verify SL extraction when only SL exists
- `test_compute_position_tp_sl_with_only_tp`: Verify TP extraction when only TP exists
- `test_compute_position_tp_sl_no_orders`: Verify behavior when no TP/SL orders exist
- `test_compute_position_tp_sl_different_symbol`: Verify symbol filtering
- `test_enrich_positions_with_tp_sl`: Verify position enrichment with TP/SL
- `test_enrich_positions_with_tp_sl_multiple_positions`: Verify multiple position enrichment

### Integration Tests (test_execution_flow.py)

These tests verify the execution flow with mocked ccxt exchange:

- `test_place_sl_tp_orders_for_long_position`: Verify TP/SL placement for LONG positions
- `test_place_sl_tp_orders_for_short_position`: Verify TP/SL placement for SHORT positions
- `test_get_tp_sl_orders_for_position`: Verify retrieval of TP/SL orders
- `test_get_tp_sl_orders_missing_sl`: Verify detection of missing SL
- `test_get_tp_sl_orders_missing_tp`: Verify detection of missing TP
- `test_cancel_and_replace_tp_sl_on_quantity_mismatch`: Verify quantity mismatch handling

## Test Design

### Mocking Strategy

The tests use Python's `unittest.mock` to mock the ccxt exchange:

```python
@patch('execution.ccxt.binance')
def test_example(self, mock_binance_class):
    mock_exchange = MagicMock()
    mock_binance_class.return_value = mock_exchange
    # ... test code
```

This allows testing the bot logic without making actual API calls to Binance.

### Test Isolation

Each test method includes a `setUp()` that resets the bot state:

```python
def setUp(self):
    state.bot_state.positions = {}
    state.bot_state.exchange_open_orders = []
    state.bot_state.pending_orders = {}
    state.bot_state.reconciliation_log = []
```

This ensures tests don't interfere with each other.

## Manual Testing

For manual testing with the live system (testnet recommended):

1. Set up environment variables in `.env`:
   ```
   BINANCE_API_KEY=your_testnet_key
   BINANCE_API_SECRET=your_testnet_secret
   BINANCE_TESTNET=True
   ```

2. Start the bot:
   ```bash
   python main.py
   ```

3. Test scenarios:
   - **New Entry Fill**: Place a limit order, wait for fill, verify TP/SL appear
   - **Restart with Position**: Stop bot with open position, restart, verify TP/SL are checked/repaired
   - **Quantity Mismatch**: Manually modify TP/SL quantity on exchange, restart bot, verify it repairs
   - **Missing TP/SL**: Cancel TP or SL order on exchange, wait for reconciliation (10 min), verify recreation

4. Use the web UI (if running via `api.py`) to monitor:
   - Position TP/SL values in `/api/positions`
   - Reconciliation logs in `/api/metrics`
   - Exchange orders in `/api/exchange-orders`

## Continuous Integration

To integrate with CI/CD:

```bash
# Add to your CI script
python tests/run_tests.py
exit_code=$?
if [ $exit_code -ne 0 ]; then
    echo "Tests failed!"
    exit 1
fi
```

## Troubleshooting

### Import Errors

If you see `ModuleNotFoundError`, ensure you're running tests from the repository root and dependencies are installed:

```bash
cd /path/to/HunterZ
pip install -r requirements.txt
python tests/run_tests.py
```

### Config Errors

Some tests may create a `.env` file. If you see config-related errors, ensure your `.env` file has valid (or dummy) values:

```
BINANCE_API_KEY=test_key
BINANCE_API_SECRET=test_secret
BINANCE_TESTNET=True
```

## Adding New Tests

To add new tests:

1. Create a new test file in `tests/` with prefix `test_`:
   ```python
   # tests/test_new_feature.py
   import unittest
   from unittest.mock import Mock, patch
   import sys
   import os
   
   sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
   
   class TestNewFeature(unittest.TestCase):
       def test_something(self):
           # Your test code
           pass
   
   if __name__ == '__main__':
       unittest.main()
   ```

2. Run the new test:
   ```bash
   python tests/run_tests.py test_new_feature
   ```

3. Verify it's included in the full test suite:
   ```bash
   python tests/run_tests.py
   ```
