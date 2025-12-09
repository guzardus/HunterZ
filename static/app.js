// HunterZ Trading System - Frontend JavaScript
// TRON-themed Order Block Trading Dashboard

const TRADING_PAIRS = [
    'BTC/USDT',
    'ETH/USDT',
    'SOL/USDT',
    'UNI/USDT',
    'DOT/USDT',
    'BNB/USDT'
];

const charts = {};
const candlestickSeries = {};
const UPDATE_INTERVAL = 5000; // Update every 5 seconds

// Initialize charts
function initializeCharts() {
    // Check if LightweightCharts is available
    if (typeof LightweightCharts === 'undefined') {
        console.warn('LightweightCharts library not loaded. Charts will not be displayed.');
        // Show a message in each chart container
        TRADING_PAIRS.forEach(symbol => {
            const symbolKey = symbol.replace('/', '');
            const chartElement = document.getElementById(`chart-${symbolKey}`);
            if (chartElement) {
                chartElement.innerHTML = '<div style="display: flex; align-items: center; justify-content: center; height: 100%; color: #666; text-align: center;">📊<br>Chart will display when data is available</div>';
            }
        });
        return;
    }
    
    TRADING_PAIRS.forEach(symbol => {
        const symbolKey = symbol.replace('/', '');
        const chartElement = document.getElementById(`chart-${symbolKey}`);
        
        if (chartElement) {
            const chart = LightweightCharts.createChart(chartElement, {
                width: chartElement.clientWidth,
                height: 300,
                layout: {
                    background: { color: '#000000' },
                    textColor: '#00ff00',
                },
                grid: {
                    vertLines: { color: '#1a0000' },
                    horzLines: { color: '#1a0000' },
                },
                crosshair: {
                    mode: LightweightCharts.CrosshairMode.Normal,
                },
                rightPriceScale: {
                    borderColor: '#ff0000',
                },
                timeScale: {
                    borderColor: '#ff0000',
                    timeVisible: true,
                    secondsVisible: false,
                },
            });

            const candleSeries = chart.addCandlestickSeries({
                upColor: '#00ff00',
                downColor: '#ff0000',
                borderUpColor: '#00ff00',
                borderDownColor: '#ff0000',
                wickUpColor: '#00ff00',
                wickDownColor: '#ff0000',
            });

            charts[symbolKey] = chart;
            candlestickSeries[symbolKey] = candleSeries;

            // Make chart responsive
            new ResizeObserver(entries => {
                if (entries.length === 0 || entries[0].target !== chartElement) {
                    return;
                }
                const newRect = entries[0].contentRect;
                chart.applyOptions({ width: newRect.width });
            }).observe(chartElement);
        }
    });
}

// Fetch and update status
async function updateStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        
        document.getElementById('balance').textContent = `${data.balance.toFixed(2)} USDT`;
        document.getElementById('total-pnl').textContent = `${data.total_pnl.toFixed(2)} USDT`;
        document.getElementById('total-pnl').className = data.total_pnl >= 0 ? 'value positive' : 'value negative';
        document.getElementById('active-positions').textContent = data.active_positions;
        
        if (data.last_update) {
            const date = new Date(data.last_update);
            document.getElementById('last-update').textContent = date.toLocaleTimeString();
        }
    } catch (error) {
        console.error('Error updating status:', error);
    }
}

// Fetch and update wallet balance
async function updateWallet() {
    try {
        const response = await fetch('/api/balance');
        const data = await response.json();
        
        document.getElementById('wallet-total').textContent = data.total.toFixed(2);
        document.getElementById('wallet-free').textContent = data.free.toFixed(2);
        document.getElementById('wallet-in-positions').textContent = data.in_positions.toFixed(2);
    } catch (error) {
        console.error('Error updating wallet:', error);
    }
}

// Fetch and update positions
async function updatePositions() {
    try {
        const response = await fetch('/api/positions');
        const data = await response.json();
        
        const tbody = document.getElementById('positions-tbody');
        
        if (data.positions && data.positions.length > 0) {
            tbody.innerHTML = data.positions.map(pos => `
                <tr>
                    <td>${pos.symbol}</td>
                    <td class="${pos.side === 'LONG' ? 'positive' : 'negative'}">${pos.side}</td>
                    <td>${pos.size.toFixed(4)}</td>
                    <td>${pos.entry_price.toFixed(2)}</td>
                    <td>${pos.mark_price.toFixed(2)}</td>
                    <td class="${pos.unrealized_pnl >= 0 ? 'positive' : 'negative'}">
                        ${pos.unrealized_pnl.toFixed(2)} USDT
                    </td>
                    <td>${pos.leverage}x</td>
                </tr>
            `).join('');
        } else {
            tbody.innerHTML = '<tr><td colspan="7" class="no-data">No active positions</td></tr>';
        }
    } catch (error) {
        console.error('Error updating positions:', error);
    }
}

// Fetch and update trade history
async function updateTrades() {
    try {
        const response = await fetch('/api/trades');
        const data = await response.json();
        
        const tbody = document.getElementById('trades-tbody');
        
        if (data.trades && data.trades.length > 0) {
            tbody.innerHTML = data.trades.slice(0, 10).map(trade => {
                const time = new Date(trade.timestamp).toLocaleString();
                return `
                    <tr>
                        <td>${time}</td>
                        <td>${trade.symbol || '-'}</td>
                        <td>${trade.side || '-'}</td>
                        <td>${trade.entry_price ? trade.entry_price.toFixed(2) : '-'}</td>
                        <td>${trade.exit_price ? trade.exit_price.toFixed(2) : '-'}</td>
                        <td class="${trade.pnl >= 0 ? 'positive' : 'negative'}">
                            ${trade.pnl ? trade.pnl.toFixed(2) : '-'} USDT
                        </td>
                        <td>${trade.status || '-'}</td>
                    </tr>
                `;
            }).join('');
        } else {
            tbody.innerHTML = '<tr><td colspan="7" class="no-data">No trades yet</td></tr>';
        }
    } catch (error) {
        console.error('Error updating trades:', error);
    }
}

// Update chart with market data
async function updateMarketData() {
    try {
        const response = await fetch('/api/all-market-data');
        const allData = await response.json();
        
        for (const [symbol, data] of Object.entries(allData)) {
            const symbolKey = symbol.replace('/', '');
            
            // Update price
            const priceElement = document.getElementById(`price-${symbolKey}`);
            if (priceElement && data.current_price) {
                priceElement.textContent = `$${data.current_price.toFixed(2)}`;
            }
            
            // Update chart data
            if (candlestickSeries[symbolKey] && data.ohlcv && data.ohlcv.length > 0) {
                candlestickSeries[symbolKey].setData(data.ohlcv);
            }
            
            // Display order blocks info
            const infoElement = document.getElementById(`info-${symbolKey}`);
            if (infoElement && data.order_blocks) {
                const bullishOBs = data.order_blocks.filter(ob => ob.type === 'bullish').length;
                const bearishOBs = data.order_blocks.filter(ob => ob.type === 'bearish').length;
                
                let infoHTML = '';
                if (bullishOBs > 0) {
                    infoHTML += `<div class="ob-info bullish">🟢 ${bullishOBs} Bullish OB</div>`;
                }
                if (bearishOBs > 0) {
                    infoHTML += `<div class="ob-info bearish">🔴 ${bearishOBs} Bearish OB</div>`;
                }
                
                // Show position info if exists
                if (data.position) {
                    const pnlClass = data.position.unrealized_pnl >= 0 ? 'bullish' : 'bearish';
                    infoHTML += `<div class="ob-info ${pnlClass}">
                        📊 ${data.position.side}: ${data.position.unrealized_pnl.toFixed(2)} USDT
                    </div>`;
                }
                
                infoElement.innerHTML = infoHTML || '<div class="no-data">No order blocks detected</div>';
                
                // Draw order blocks on chart
                drawOrderBlocks(symbolKey, data.order_blocks, data.position);
            }
        }
    } catch (error) {
        console.error('Error updating market data:', error);
    }
}

// Draw order blocks on chart
function drawOrderBlocks(symbolKey, orderBlocks, position) {
    const chart = charts[symbolKey];
    if (!chart || !orderBlocks) return;
    
    // Remove existing markers
    const series = candlestickSeries[symbolKey];
    
    // Add markers for order blocks
    const markers = [];
    
    orderBlocks.forEach(ob => {
        if (ob.type === 'bullish') {
            markers.push({
                time: ob.time,
                position: 'belowBar',
                color: '#00ff00',
                shape: 'arrowUp',
                text: `Bull OB: ${ob.ob_top.toFixed(2)}`
            });
        } else if (ob.type === 'bearish') {
            markers.push({
                time: ob.time,
                position: 'aboveBar',
                color: '#ff0000',
                shape: 'arrowDown',
                text: `Bear OB: ${ob.ob_bottom.toFixed(2)}`
            });
        }
    });
    
    // Add position markers
    if (position) {
        // Note: We'd need position entry time to mark it properly
        // For now, just showing in the info box
    }
    
    if (markers.length > 0) {
        series.setMarkers(markers);
    }
}

// Update all data
async function updateAll() {
    await Promise.all([
        updateStatus(),
        updateWallet(),
        updatePositions(),
        updateTrades(),
        updateMarketData()
    ]);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    console.log('HunterZ Trading System - Initializing...');
    
    // Initialize charts
    initializeCharts();
    
    // Initial update
    updateAll();
    
    // Set up periodic updates
    setInterval(updateAll, UPDATE_INTERVAL);
    
    console.log('HunterZ Trading System - Ready');
});

// Handle window resize
window.addEventListener('resize', () => {
    Object.values(charts).forEach(chart => {
        chart.resize();
    });
});
