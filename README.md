# HunterZ - Order Block Trading System

A sophisticated cryptocurrency trading bot based on the LuxAlgo Order Block detection strategy, featuring a TRON-themed frontend dashboard with real-time charts.

## Features

- **30-Minute Order Block Strategy**: Implements the proven LuxAlgo Order Block detection algorithm
- **Multi-Pair Trading**: Trades 6 major cryptocurrency pairs:
  - BTC/USDT
  - ETH/USDT
  - SOL/USDT
  - UNI/USDT
  - DOT/USDT
  - BNB/USDT
- **Persistent Order Tracking**: 
  - Pending orders are saved to disk and persist across restarts
  - Automatic reconciliation of exchange orders at startup
  - Handles partial fills with automatic TP/SL placement
- **Order Reconciliation**:
  - At startup, bot fetches all open orders from exchange
  - Matches orders with current strategy (order blocks)
  - Cancels orphaned orders that don't match any active strategy
- **Comprehensive Metrics**:
  - Pending orders count
  - Open exchange orders count
  - Placed, cancelled, and filled orders tracking
  - Recent reconciliation actions log
- **TRON-Themed Frontend**: Sleek black background with red highlights and cyberpunk aesthetics
- **Real-Time Charts**: TradingView lightweight charts showing:
  - 30-minute candlesticks
  - Order block markers (bullish/bearish)
  - Entry/exit points
  - Take profit and stop loss levels
- **Live Trading Dashboard**:
  - Wallet balance in USDT
  - Active positions with unrealized P&L
  - Trade history
  - Order block information
  - Real-time price updates

## Installation

1. Clone the repository:
```bash
git clone https://github.com/guzardus/HunterZ.git
cd HunterZ
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure your Binance API credentials:
```bash
cp .env.example .env
# Edit .env with your actual API credentials
```

## Configuration

Edit the `.env` file with your Binance API credentials:

```
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
BINANCE_TESTNET=True  # Set to False for production trading
```

**Important**: 
- Start with testnet mode (BINANCE_TESTNET=True) to test the system
- Only switch to production after thorough testing
- Never share your API keys

## Usage

### Starting the Trading Bot with Web Interface

Run the API server which includes both the trading bot and web interface:

```bash
python api.py
```

The system will:
1. Start the trading bot in the background
2. Launch the web server on http://localhost:8000

Access the dashboard at: **http://localhost:8000**

### Running the Bot Only (No Web Interface)

If you only want to run the trading bot without the web interface:

```bash
python main.py
```

## Trading Strategy

The bot implements the LuxAlgo Order Block strategy:

1. **Order Block Detection**: Identifies volume pivots that signal institutional activity
2. **Market Structure**: Validates order blocks based on price breaking key levels
3. **Entry Logic**: Places limit orders at order block boundaries
4. **Risk Management**: 
   - Fixed risk per trade (1% of balance)
   - Risk-reward ratio of 2:1
   - Automatic stop loss and take profit placement
5. **Cycle Time**: Bot evaluates opportunities every 2 minutes (120 seconds)

## Frontend Features

### Dashboard Sections

1. **Header Status Bar**: Quick overview of balance, P&L, active positions
2. **Wallet Overview**: Total USDT balance, available funds, funds in positions
3. **Live Trading Charts**: Six charts showing real-time data with order blocks
4. **Active Positions Table**: Details of all open positions
5. **Trade History**: Recent completed trades

### Color Coding

- **Green**: Bullish order blocks, positive P&L, long positions
- **Red**: Bearish order blocks, negative P&L, short positions
- **TRON Aesthetics**: Cyberpunk-inspired black background with red accents

## API Endpoints

- `GET /` - Main dashboard
- `GET /api/status` - Bot status and general info
- `GET /api/balance` - Wallet balance details
- `GET /api/positions` - Active positions
- `GET /api/trades` - Trade history
- `GET /api/market-data/{symbol}` - Market data for specific pair
- `GET /api/all-market-data` - Market data for all pairs
- `GET /api/metrics` - Order metrics and reconciliation log

## Safety Features

- Testnet support for risk-free testing
- Position size limits based on available balance
- Stop loss on every trade
- Order cancellation before new entries
- Error handling and logging
- **Persistent state**: Pending orders saved to `data/pending_orders.json`
- **Startup reconciliation**: Validates and reconciles all exchange orders at bot startup
- **Orphan order handling**: Automatically cancels orders that don't match current strategy
- **Partial fill handling**: Places TP/SL for partial fills and tracks remaining quantity
- **TP/SL Reconciliation**: 
  - Automatically repairs missing TP/SL orders for open positions
  - Detects and fixes TP/SL quantity mismatches
  - Runs at startup and every 10 minutes
  - Derives TP/SL from exchange orders for accurate display

## Development

### Project Structure

```
HunterZ/
├── api.py              # FastAPI web server and API endpoints
├── main.py             # Main trading bot logic
├── config.py           # Configuration and settings
├── lux_algo.py         # Order block detection algorithm
├── execution.py        # Binance exchange interface
├── risk_manager.py     # Risk management and position sizing
├── state.py            # Global state management
├── utils.py            # Utility functions
├── tests/              # Automated tests
│   ├── __init__.py
│   ├── run_tests.py    # Test runner
│   ├── test_tp_sl_reconciliation.py  # Unit tests
│   ├── test_execution_flow.py        # Integration tests
│   └── README.md       # Testing documentation
├── static/             # Frontend files
│   ├── index.html      # Main dashboard HTML
│   ├── style.css       # TRON-themed styles
│   └── app.js          # Frontend logic and charts
├── requirements.txt    # Python dependencies
└── .env.example        # Environment variables template
```

### Running Tests

The project includes comprehensive automated tests for TP/SL management:

```bash
# Run all tests
python tests/run_tests.py

# Run with verbose output
python tests/run_tests.py -v

# Run specific test file
python tests/run_tests.py test_tp_sl_reconciliation
```

For detailed testing documentation, see [tests/README.md](tests/README.md).

Test coverage includes:
- TP/SL derivation from exchange orders
- Position reconciliation logic
- Order placement flow with mocked exchange
- Quantity mismatch detection and repair
- Missing TP/SL detection and creation

## Troubleshooting

### Connection Issues
- Ensure your API keys are correct
- Check if Binance API is accessible from your region
- Verify testnet mode setting matches your API keys

### Charts Not Displaying
- The frontend uses TradingView Lightweight Charts from CDN
- If CDN is blocked, charts will show a placeholder message
- For production deployments with restricted internet, consider hosting the chart library locally
- The system functions correctly without charts; they are for visualization only

### No Order Blocks Detected
- Order blocks take time to form
- The algorithm requires sufficient market movement
- Check that OHLCV data is being fetched successfully

### Frontend Not Loading
- Ensure the API server is running on port 8000
- Check browser console for errors
- Verify static files are in the correct directory

## Disclaimer

**This is trading software. Use at your own risk.**

- Cryptocurrency trading carries significant risk of loss
- Past performance does not guarantee future results
- Always start with testnet mode
- Only trade with funds you can afford to lose
- The authors are not responsible for any financial losses

## Testing the New Features

### Automated Tests
The bot includes comprehensive automated tests:
```bash
python tests/run_tests.py -v
```
See [tests/README.md](tests/README.md) for details.

### TP/SL Reconciliation
The bot now automatically ensures all positions have proper TP/SL orders:

**At Startup:**
- Checks all open positions for missing or mismatched TP/SL orders
- Places missing TP/SL orders with correct quantities
- Cancels and replaces TP/SL orders with wrong quantities

**During Operation:**
- Runs reconciliation every 10 minutes
- Logs all actions to the reconciliation log
- Derives TP/SL from exchange orders for accurate display

**Testing Scenarios:**
1. **Manual Repair Test**:
   - Start bot with testnet
   - Place a trade and wait for entry fill
   - Manually cancel SL or TP order on Binance UI
   - Wait for next reconciliation cycle (up to 10 min) or restart bot
   - Verify missing order is recreated

2. **Quantity Mismatch Test**:
   - Open a position
   - Manually modify TP/SL order quantity on Binance
   - Restart bot or wait for reconciliation
   - Verify old orders are cancelled and new ones created with correct size

3. **Restart Test**:
   - Stop bot with open position
   - Restart bot
   - Check console for position reconciliation output
   - Verify TP/SL are still present and correct

### Persistent State
- Pending orders are automatically saved to `data/pending_orders.json`
- Stop the bot and restart it to verify orders persist
- Check the file to inspect persisted order data

### Startup Reconciliation
- When the bot starts, it will:
  1. Load persisted pending orders from disk
  2. Fetch all open orders from the exchange
  3. Match orders with pending orders and current order blocks
  4. Cancel orphaned orders that don't match strategy
  5. Check all positions for proper TP/SL orders
  6. Log all reconciliation actions
- Check the console output for reconciliation logs
- View the "Recent Reconciliation Actions" section in the UI

### Metrics Dashboard
- Access the dashboard at http://localhost:8000
- View metrics in the header:
  - Pending Orders: Count of orders being tracked
  - Exchange Orders: Open orders on exchange (from last reconciliation)
  - Placed: Total orders placed by the bot
  - Cancelled: Total orders cancelled
  - Filled: Total orders filled
- Recent actions log shows the last 50 reconciliation events
- Position TP/SL values are derived from actual exchange orders

### Partial Fills
- If an order is partially filled:
  - TP/SL orders are placed for the filled portion
  - The pending order is updated with remaining quantity
  - Changes are persisted to disk
- Monitor console logs for partial fill handling

## License

This project is provided as-is for educational purposes.

## Credits

Based on the LuxAlgo Order Block detection strategy with TRON-inspired aesthetics.
