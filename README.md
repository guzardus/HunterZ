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

## Safety Features

- Testnet support for risk-free testing
- Position size limits based on available balance
- Stop loss on every trade
- Order cancellation before new entries
- Error handling and logging

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
├── static/             # Frontend files
│   ├── index.html      # Main dashboard HTML
│   ├── style.css       # TRON-themed styles
│   └── app.js          # Frontend logic and charts
├── requirements.txt    # Python dependencies
└── .env.example        # Environment variables template
```

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

## License

This project is provided as-is for educational purposes.

## Credits

Based on the LuxAlgo Order Block detection strategy with TRON-inspired aesthetics.
