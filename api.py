from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import uvicorn
import state
import main
import config
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start the bot loop in background
    main.start_bot_thread()
    yield
    # Shutdown: cleanup if needed

app = FastAPI(lifespan=lifespan)

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (frontend)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def serve_frontend():
    """Serve the main frontend page"""
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "HunterZ Trading Bot API - Frontend not found"}

@app.get("/api/status")
def get_status():
    """Get overall bot status"""
    return {
        "balance": state.bot_state.balance,
        "total_pnl": state.bot_state.total_pnl,
        "last_update": state.bot_state.last_update,
        "trading_pairs": config.TRADING_PAIRS,
        "active_positions": len(state.bot_state.positions)
    }

@app.get("/api/balance")
def get_balance():
    """Get wallet balance in USDT"""
    total_in_positions = sum(
        pos.get('entry_price', 0) * pos.get('size', 0) 
        for pos in state.bot_state.positions.values()
    )
    return {
        "total": state.bot_state.balance,
        "free": state.bot_state.balance - total_in_positions,
        "in_positions": total_in_positions,
        "currency": "USDT"
    }

@app.get("/api/positions")
def get_positions():
    """Get all active positions"""
    return {
        "positions": list(state.bot_state.positions.values())
    }

@app.get("/api/trades")
def get_trades():
    """Get trade history"""
    return {
        "trades": state.bot_state.trade_history
    }

@app.get("/api/market-data/{symbol}")
def get_market_data(symbol: str):
    """Get market data for a specific symbol"""
    # Normalize symbol format
    decoded_symbol = symbol.replace('-', '/').upper()
    if '/' not in decoded_symbol:
        decoded_symbol = decoded_symbol.replace('USDT', '/USDT')
    
    ohlcv = state.bot_state.ohlcv_data.get(decoded_symbol, [])
    obs = state.bot_state.order_blocks.get(decoded_symbol, [])
    position = state.bot_state.positions.get(decoded_symbol)
    
    return {
        "symbol": decoded_symbol,
        "ohlcv": ohlcv,
        "order_blocks": obs,
        "position": position
    }

@app.get("/api/all-market-data")
def get_all_market_data():
    """Get market data for all trading pairs"""
    result = {}
    for symbol in config.TRADING_PAIRS:
        ohlcv = state.bot_state.ohlcv_data.get(symbol, [])
        obs = state.bot_state.order_blocks.get(symbol, [])
        position = state.bot_state.positions.get(symbol)
        
        result[symbol] = {
            "symbol": symbol,
            "ohlcv": ohlcv,
            "order_blocks": obs,
            "position": position,
            "current_price": ohlcv[-1]['close'] if ohlcv else 0
        }
    return result

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
