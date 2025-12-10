// HunterZ Trading System - Frontend JavaScript
// Ethereum.org inspired design with comprehensive dashboard

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
const orderBlockSeries = {};
const markerSeries = {};
const UPDATE_INTERVAL = 30000; // Update every 30 seconds for better responsiveness
let lastUpdateTime = Date.now();
let limitOrdersCount = 0;

// Melbourne timezone offset (AEDT is UTC+11, AEST is UTC+10)
function getMelbourneTime() {
    return new Date().toLocaleString('en-AU', { 
        timeZone: 'Australia/Melbourne',
        hour: '2-digit',
        minute: '2-digit', 
        second: '2-digit',
        hour12: false
    });
}

// Update refresh timer
function updateRefreshTimer() {
    const elapsed = Date.now() - lastUpdateTime;
    const remaining = Math.max(0, Math.ceil((UPDATE_INTERVAL - elapsed) / 1000));
    document.getElementById('refresh-timer').textContent = `${remaining}s`;
}

// Update Melbourne time
function updateMelbourneTime() {
    document.getElementById('melbourne-time').textContent = getMelbourneTime();
}

// Initialize charts with Ethereum.org style colors
function initializeCharts() {
    if (typeof LightweightCharts === 'undefined') {
        console.warn('LightweightCharts library not loaded. Charts will not be displayed.');
        TRADING_PAIRS.forEach(symbol => {
            const symbolKey = symbol.replace('/', '');
            const chartElement = document.getElementById(`chart-${symbolKey}`);
            if (chartElement) {
                chartElement.innerHTML = '<div style="display: flex; align-items: center; justify-content: center; height: 100%; color: #94a3b8; text-align: center;">📊<br>Chart will display when data is available</div>';
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
                    background: { 
                        type: 'solid',
                        color: 'rgba(255, 255, 255, 0.5)'
                    },
                    textColor: '#475569',
                },
                grid: {
                    vertLines: { 
                        color: 'rgba(59, 130, 246, 0.05)',
                        style: 1,
                    },
                    horzLines: { 
                        color: 'rgba(59, 130, 246, 0.05)',
                        style: 1,
                    },
                },
                crosshair: {
                    mode: LightweightCharts.CrosshairMode.Normal,
                    vertLine: {
                        color: 'rgba(59, 130, 246, 0.4)',
                        width: 1,
                        style: 2,
                    },
                    horzLine: {
                        color: 'rgba(59, 130, 246, 0.4)',
                        width: 1,
                        style: 2,
                    },
                },
                rightPriceScale: {
                    borderColor: 'rgba(59, 130, 246, 0.2)',
                    textColor: '#475569',
                },
                timeScale: {
                    borderColor: 'rgba(59, 130, 246, 0.2)',
                    textColor: '#475569',
                    timeVisible: true,
                    secondsVisible: false,
                },
            });

            const candleSeries = chart.addCandlestickSeries({
                upColor: '#10b981',
                downColor: '#ef4444',
                borderUpColor: '#10b981',
                borderDownColor: '#ef4444',
                wickUpColor: '#10b981',
                wickDownColor: '#ef4444',
            });

            charts[symbolKey] = chart;
            candlestickSeries[symbolKey] = candleSeries;
            orderBlockSeries[symbolKey] = []; // Initialize order block series array

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
        
        // Calculate total unrealized P&L from positions
        let totalUnrealizedPnL = 0;
        if (data.positions) {
            Object.values(data.positions).forEach(pos => {
                totalUnrealizedPnL += pos.unrealized_pnl || 0;
            });
        }
        
        // Update header values
        document.getElementById('balance').textContent = `${data.balance.toFixed(2)} USDT`;
        document.getElementById('unrealized-pnl').textContent = `${totalUnrealizedPnL.toFixed(2)} USDT`;
        document.getElementById('unrealized-pnl').className = totalUnrealizedPnL >= 0 ? 'value positive' : 'value negative';
        
        // Calculate total balance (wallet + unrealized P&L)
        const totalBalance = data.balance + totalUnrealizedPnL;
        document.getElementById('total-balance').textContent = `${totalBalance.toFixed(2)} USDT`;
        document.getElementById('total-balance').className = totalBalance >= data.balance ? 'value positive' : 'value negative';
        
        // Update additional info
        document.getElementById('active-positions-count').textContent = data.active_positions;
        document.getElementById('total-pnl').textContent = `${data.total_pnl.toFixed(2)} USDT`;
        document.getElementById('total-pnl').className = data.total_pnl >= 0 ? 'value positive' : 'value negative';
        
        lastUpdateTime = Date.now();
    } catch (error) {
        console.error('Error updating status:', error);
    }
}

// Fetch and update wallet balance (not used in new design but keeping for compatibility)
async function updateWallet() {
    try {
        const response = await fetch('/api/balance');
        const data = await response.json();
        // Data still available if needed elsewhere
    } catch (error) {
        console.error('Error updating wallet:', error);
    }
}

// Fetch and update positions with TP/SL info
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
                    <td>$${pos.entry_price.toFixed(2)}</td>
                    <td>$${pos.mark_price.toFixed(2)}</td>
                    <td class="${pos.unrealized_pnl >= 0 ? 'positive' : 'negative'}">
                        ${pos.unrealized_pnl.toFixed(2)} USDT
                    </td>
                    <td>${pos.leverage}x</td>
                    <td>${pos.take_profit ? '$' + pos.take_profit.toFixed(2) : '-'}</td>
                    <td>${pos.stop_loss ? '$' + pos.stop_loss.toFixed(2) : '-'}</td>
                </tr>
            `).join('');
        } else {
            tbody.innerHTML = '<tr><td colspan="9" class="no-data">No active positions</td></tr>';
        }
    } catch (error) {
        console.error('Error updating positions:', error);
    }
}

// Fetch and update trade history with comprehensive data
async function updateTrades() {
    try {
        const response = await fetch('/api/trades');
        const data = await response.json();
        
        const tbody = document.getElementById('trades-tbody');
        
        if (data.trades && data.trades.length > 0) {
            // Calculate win rate
            const closedTrades = data.trades.filter(t => t.status === 'CLOSED' || t.pnl !== undefined);
            const winningTrades = closedTrades.filter(t => t.pnl > 0);
            const winRate = closedTrades.length > 0 ? (winningTrades.length / closedTrades.length * 100).toFixed(1) : 0;
            document.getElementById('win-rate').textContent = `${winRate}%`;
            document.getElementById('win-rate').className = winRate >= 50 ? 'value positive' : 'value negative';
            
            tbody.innerHTML = data.trades.slice(0, 20).map(trade => {
                // Convert to Melbourne time
                const time = new Date(trade.timestamp).toLocaleString('en-AU', { 
                    timeZone: 'Australia/Melbourne',
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit'
                });
                
                // Calculate P&L percentage
                let pnlPercent = '-';
                if (trade.entry_price && trade.pnl && trade.size && trade.size > 0) {
                    pnlPercent = ((trade.pnl / (trade.entry_price * trade.size)) * 100).toFixed(2);
                }
                
                // Calculate duration
                let duration = '-';
                if (trade.entry_time && trade.exit_time) {
                    const durationMs = new Date(trade.exit_time) - new Date(trade.entry_time);
                    const hours = Math.floor(durationMs / 3600000);
                    const minutes = Math.floor((durationMs % 3600000) / 60000);
                    duration = hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;
                }
                
                return `
                    <tr>
                        <td>${time}</td>
                        <td><strong>${trade.symbol || '-'}</strong></td>
                        <td class="${(trade.side === 'BUY' || trade.side === 'LONG') ? 'positive' : 'negative'}">${trade.side || '-'}</td>
                        <td>$${trade.entry_price ? trade.entry_price.toFixed(2) : '-'}</td>
                        <td>$${trade.exit_price ? trade.exit_price.toFixed(2) : '-'}</td>
                        <td>${trade.size ? trade.size.toFixed(4) : '-'}</td>
                        <td class="${trade.pnl >= 0 ? 'positive' : 'negative'}">
                            ${trade.pnl ? trade.pnl.toFixed(2) : '-'} USDT
                        </td>
                        <td class="${trade.pnl >= 0 ? 'positive' : 'negative'}">
                            ${pnlPercent !== '-' ? pnlPercent + '%' : '-'}
                        </td>
                        <td>${duration}</td>
                        <td><span class="info-badge ${trade.status === 'CLOSED' ? 'success' : ''}">${trade.status || '-'}</span></td>
                    </tr>
                `;
            }).join('');
        } else {
            tbody.innerHTML = '<tr><td colspan="10" class="no-data">No trades yet</td></tr>';
            document.getElementById('win-rate').textContent = '0%';
        }
    } catch (error) {
        console.error('Error updating trades:', error);
    }
}

// Update chart with market data and draw order blocks
async function updateMarketData() {
    try {
        const response = await fetch('/api/all-market-data');
        const allData = await response.json();
        
        limitOrdersCount = 0;
        
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
            
            // Display order blocks info with detailed information
            const infoElement = document.getElementById(`info-${symbolKey}`);
            if (infoElement && data.order_blocks) {
                const bullishOBs = data.order_blocks.filter(ob => ob.type === 'bullish');
                const bearishOBs = data.order_blocks.filter(ob => ob.type === 'bearish');
                
                limitOrdersCount += bullishOBs.length + bearishOBs.length;
                
                let infoHTML = '';
                
                // Show bullish order blocks
                if (bullishOBs.length > 0) {
                    infoHTML += `<div class="ob-info bullish">🟢 ${bullishOBs.length} Bullish OB`;
                    const latestBullish = bullishOBs[0];
                    if (latestBullish) {
                        infoHTML += ` @ $${latestBullish.ob_top ? latestBullish.ob_top.toFixed(2) : 'N/A'}`;
                    }
                    infoHTML += '</div>';
                }
                
                // Show bearish order blocks
                if (bearishOBs.length > 0) {
                    infoHTML += `<div class="ob-info bearish">🔴 ${bearishOBs.length} Bearish OB`;
                    const latestBearish = bearishOBs[0];
                    if (latestBearish) {
                        infoHTML += ` @ $${latestBearish.ob_bottom ? latestBearish.ob_bottom.toFixed(2) : 'N/A'}`;
                    }
                    infoHTML += '</div>';
                }
                
                // Show position info if exists
                if (data.position) {
                    const pnlClass = data.position.unrealized_pnl >= 0 ? 'bullish' : 'bearish';
                    const side = data.position.side === 'LONG' ? '📈' : '📉';
                    infoHTML += `<div class="ob-info ${pnlClass}">
                        ${side} ${data.position.side}: ${data.position.unrealized_pnl.toFixed(2)} USDT
                    </div>`;
                    
                    // Show TP and SL if available
                    if (data.position.take_profit || data.position.stop_loss) {
                        infoHTML += `<div class="ob-info">`;
                        if (data.position.take_profit) {
                            infoHTML += `TP: $${data.position.take_profit.toFixed(2)} `;
                        }
                        if (data.position.stop_loss) {
                            infoHTML += `SL: $${data.position.stop_loss.toFixed(2)}`;
                        }
                        infoHTML += `</div>`;
                    }
                }
                
                infoElement.innerHTML = infoHTML || '<div class="no-data">No order blocks detected</div>';
                
                // Draw order blocks and markers on chart
                drawOrderBlocks(symbolKey, data.order_blocks, data.position);
            }
        }
        
        // Update limit orders count
        document.getElementById('limit-orders-count').textContent = limitOrdersCount;
        
    } catch (error) {
        console.error('Error updating market data:', error);
    }
}

// Draw order blocks on chart with zones, entry, TP, and SL
function drawOrderBlocks(symbolKey, orderBlocks, position) {
    const chart = charts[symbolKey];
    if (!chart || !orderBlocks) return;
    
    const series = candlestickSeries[symbolKey];
    
    // Clear existing markers
    series.setMarkers([]);
    
    // Remove existing order block series
    if (orderBlockSeries[symbolKey] && orderBlockSeries[symbolKey].length > 0) {
        orderBlockSeries[symbolKey].forEach(s => {
            try {
                chart.removeSeries(s);
            } catch (e) {
                console.warn(`Could not remove series for ${symbolKey}:`, e.message);
            }
        });
        orderBlockSeries[symbolKey] = [];
    } else if (!orderBlockSeries[symbolKey]) {
        orderBlockSeries[symbolKey] = [];
    }
    
    const markers = [];
    
    // Draw order block zones as rectangles
    orderBlocks.forEach(ob => {
        if (!ob.time || !ob.ob_top || !ob.ob_bottom) return;
        
        // Create a line series for the order block zone
        const lineSeries = chart.addLineSeries({
            color: ob.type === 'bullish' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)',
            lineWidth: 0,
            lastValueVisible: false,
            priceLineVisible: false,
        });
        
        // Draw the zone using price lines
        const priceLineTop = {
            price: ob.ob_top,
            color: ob.type === 'bullish' ? '#10b981' : '#ef4444',
            lineWidth: 1,
            lineStyle: 2, // Dashed
            axisLabelVisible: true,
            title: ob.type === 'bullish' ? '🟢 OB Top' : '🔴 OB Top',
        };
        
        const priceLineBottom = {
            price: ob.ob_bottom,
            color: ob.type === 'bullish' ? '#10b981' : '#ef4444',
            lineWidth: 1,
            lineStyle: 2, // Dashed
            axisLabelVisible: true,
            title: ob.type === 'bullish' ? '🟢 OB Bot' : '🔴 OB Bot',
        };
        
        series.createPriceLine(priceLineTop);
        series.createPriceLine(priceLineBottom);
        
        orderBlockSeries[symbolKey].push(lineSeries);
        
        // Add marker at the order block location
        if (ob.type === 'bullish') {
            markers.push({
                time: ob.time,
                position: 'belowBar',
                color: '#10b981',
                shape: 'arrowUp',
                text: `Bullish OB`,
                size: 1
            });
        } else if (ob.type === 'bearish') {
            markers.push({
                time: ob.time,
                position: 'aboveBar',
                color: '#ef4444',
                shape: 'arrowDown',
                text: `Bearish OB`,
                size: 1
            });
        }
    });
    
    // Add position markers (Entry, TP, SL)
    if (position && position.entry_price) {
        // Entry marker
        const entryLine = {
            price: position.entry_price,
            color: '#3b82f6',
            lineWidth: 2,
            lineStyle: 0, // Solid
            axisLabelVisible: true,
            title: '🎯 Entry',
        };
        series.createPriceLine(entryLine);
        
        // Take Profit marker
        if (position.take_profit) {
            const tpLine = {
                price: position.take_profit,
                color: '#10b981',
                lineWidth: 2,
                lineStyle: 0,
                axisLabelVisible: true,
                title: '✅ TP',
            };
            series.createPriceLine(tpLine);
        }
        
        // Stop Loss marker
        if (position.stop_loss) {
            const slLine = {
                price: position.stop_loss,
                color: '#ef4444',
                lineWidth: 2,
                lineStyle: 0,
                axisLabelVisible: true,
                title: '❌ SL',
            };
            series.createPriceLine(slLine);
        }
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
    
    // Update Melbourne time immediately and every second
    updateMelbourneTime();
    setInterval(updateMelbourneTime, 1000);
    
    // Update refresh timer every second
    setInterval(updateRefreshTimer, 1000);
    
    // Set up periodic updates for data
    setInterval(updateAll, UPDATE_INTERVAL);
    
    console.log('HunterZ Trading System - Ready');
});

// Handle window resize
window.addEventListener('resize', () => {
    Object.values(charts).forEach(chart => {
        chart.resize();
    });
});
