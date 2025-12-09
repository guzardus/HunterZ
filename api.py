from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import state
import main
import config

app = FastAPI()

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    # Start the bot loop in background
    main.start_bot_thread()

@app.get("/status")
def get_status():
    return {
        "balance": state.bot_state.balance,
        "last_update": state.bot_state.last_update,
        "trading_pairs": config.TRADING_PAIRS
    }

@app.get("/market-data")
def get_market_data(symbol: str):
    # Determine the actual key used in state (might have slash or not)
    # The utils/config uses 'BTC/USDT'.
    # URL encoded slash might be an issue, users usually request "BTCUSDT" or "BTC-USDT"
    # Let's try to match.
    
    # Try exact match first
    decoded_symbol = symbol.replace('-', '/').replace('_', '/')
    
    ohlcv = state.bot_state.ohlcv_data.get(decoded_symbol, [])
    obs = state.bot_state.order_blocks.get(decoded_symbol, [])
    
    return {
        "symbol": decoded_symbol,
        "ohlcv": ohlcv,
        "order_blocks": obs
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
