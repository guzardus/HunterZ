// HunterZ Trading System - Frontend JavaScript
// Ethereum.org inspired design with comprehensive dashboard

const TRADING_PAIRS = [
    'BTC/USDT',
    'ETH/USDT',
    'SOL/USDT',
    'UNI/USDT',
    'DOT/USDT',
    'BNB/USDT',
    'ADA/USDT',
    'LTC/USDT',
    'AVAX/USDT',
    'XRP/USDT',
    'DOGE/USDT',
    'MATIC/USDT',
    'SHIB/USDT'
];

const charts = {};
const candlestickSeries = {};
const orderBlockSeries = {};
const markerSeries = {};
let portfolioChart = null;
let portfolioSeries = null;
const UPDATE_INTERVAL = 300000; // Update every 5 minutes (300 seconds)
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
    const timerElement = document.getElementById('refresh-timer');
    if (timerElement) {
        timerElement.textContent = `${remaining}s`;
    }
}

// Update Melbourne time (no longer displayed in new design)
function updateMelbourneTime() {
    const timeElement = document.getElementById('melbourne-time');
    if (timeElement) {
        timeElement.textContent = getMelbourneTime();
    }
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
                height: 180,
                layout: {
                    background: { 
                        type: 'solid',
                        color: 'transparent'
                    },
                    textColor: 'rgba(255, 255, 255, 0.6)',
                },
                grid: {
                    vertLines: { 
                        color: 'rgba(255, 255, 255, 0.02)',
                        style: 1,
                    },
                    horzLines: { 
                        color: 'rgba(255, 255, 255, 0.05)',
                        style: 1,
                    },
                },
                crosshair: {
                    mode: LightweightCharts.CrosshairMode.Normal,
                    vertLine: {
                        color: 'rgba(255, 255, 255, 0.2)',
                        width: 1,
                        style: 2,
                    },
                    horzLine: {
                        color: 'rgba(255, 255, 255, 0.2)',
                        width: 1,
                        style: 2,
                    },
                },
                rightPriceScale: {
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    textColor: 'rgba(255, 255, 255, 0.6)',
                },
                timeScale: {
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    textColor: 'rgba(255, 255, 255, 0.6)',
                    timeVisible: true,
                    secondsVisible: false,
                },
            });

            const candleSeries = chart.addCandlestickSeries({
                upColor: '#FFFFFF',
                downColor: '#F43F5E',
                borderUpColor: '#FFFFFF',
                borderDownColor: '#F43F5E',
                wickUpColor: '#FFFFFF',
                wickDownColor: '#F43F5E',
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

// Initialize portfolio chart
function initializePortfolioChart() {
    if (typeof LightweightCharts === 'undefined') {
        console.warn('LightweightCharts library not loaded. Portfolio chart will not be displayed.');
        const chartElement = document.getElementById('portfolio-chart');
        if (chartElement) {
            chartElement.innerHTML = '<div class="chart-fallback">📊<br>Portfolio chart will display when data is available</div>';
        }
        return;
    }
    
    const chartElement = document.getElementById('portfolio-chart');
    if (!chartElement) return;
    
    portfolioChart = LightweightCharts.createChart(chartElement, {
        width: chartElement.clientWidth,
        height: 300,
        layout: {
            background: { 
                type: 'solid',
                color: 'transparent'
            },
            textColor: 'rgba(255, 255, 255, 0.7)',
        },
        grid: {
            vertLines: { 
                color: 'rgba(255, 255, 255, 0.02)',
                style: 1,
            },
            horzLines: { 
                color: 'rgba(255, 255, 255, 0.05)',
                style: 1,
            },
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
            vertLine: {
                color: 'rgba(255, 255, 255, 0.3)',
                width: 1,
                style: 2,
            },
            horzLine: {
                color: 'rgba(255, 255, 255, 0.3)',
                width: 1,
                style: 2,
            },
        },
        rightPriceScale: {
            borderColor: 'rgba(255, 255, 255, 0.1)',
            scaleMargins: {
                top: 0.1,
                bottom: 0.1,
            },
        },
        timeScale: {
            borderColor: 'rgba(255, 255, 255, 0.1)',
            timeVisible: true,
            secondsVisible: false,
        },
    });
    
    // Create area series for portfolio balance
    portfolioSeries = portfolioChart.addAreaSeries({
        topColor: 'rgba(74, 222, 128, 0.4)',
        bottomColor: 'rgba(74, 222, 128, 0.05)',
        lineColor: '#4ADE80',
        lineWidth: 2,
        crosshairMarkerVisible: true,
        crosshairMarkerRadius: 4,
        lastValueVisible: true,
        priceLineVisible: true,
    });
    
    // Make chart responsive
    new ResizeObserver(entries => {
        if (entries.length === 0 || entries[0].target !== chartElement) {
            return;
        }
        const newRect = entries[0].contentRect;
        portfolioChart.applyOptions({ width: newRect.width });
    }).observe(chartElement);
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
        const parsedBalance = Number(data.balance);
        const equityBalance = Number.isFinite(parsedBalance) ? parsedBalance : 0;
        const parsedFreeBalance = Number(data.free_balance);
        const walletBalance = Number.isFinite(parsedFreeBalance) 
            ? parsedFreeBalance 
            : Math.max(0, equityBalance - totalUnrealizedPnL);

        const balanceElement = document.getElementById('balance');
        if (balanceElement) {
            balanceElement.textContent = walletBalance.toFixed(2);
        }
        
        const unrealizedPnlElement = document.getElementById('unrealized-pnl');
        if (unrealizedPnlElement) {
            unrealizedPnlElement.textContent = `${totalUnrealizedPnL.toFixed(2)}`;
            unrealizedPnlElement.className = totalUnrealizedPnL >= 0 ? 'stat-val value text-green' : 'stat-val value text-red';
        }
        
        // Total balance = wallet balance + unrealized P&L
        const totalBalance = Number.isFinite(parsedBalance) 
            ? equityBalance 
            : walletBalance + totalUnrealizedPnL;
        const totalBalanceElement = document.getElementById('total-balance');
        if (totalBalanceElement) {
            totalBalanceElement.textContent = totalBalance.toFixed(2);
            totalBalanceElement.className = totalBalance >= walletBalance ? 'value' : 'value text-red';
        }
        
        // Update additional info
        const activePositionsElement = document.getElementById('active-positions-count');
        if (activePositionsElement) {
            activePositionsElement.textContent = data.active_positions;
        }
        
        const totalPnlElement = document.getElementById('total-pnl');
        if (totalPnlElement) {
            totalPnlElement.textContent = `${data.total_pnl.toFixed(2)}`;
            totalPnlElement.className = data.total_pnl >= 0 ? 'stat-val value text-green' : 'stat-val value text-red';
        }
        
        lastUpdateTime = Date.now();
    } catch (error) {
        console.error('Error updating status:', error);
    }
}

// Fetch and update metrics
async function updateMetrics() {
    try {
        const response = await fetch('/api/metrics');
        const data = await response.json();
        
        // Update metrics
        const metrics = data.metrics;
        
        const pendingOrdersElement = document.getElementById('pending-orders-metric');
        if (pendingOrdersElement) {
            pendingOrdersElement.textContent = metrics.pending_orders_count;
        }
        
        const exchangeOrdersElement = document.getElementById('exchange-orders-metric');
        if (exchangeOrdersElement) {
            exchangeOrdersElement.textContent = metrics.open_exchange_orders_count;
        }
        
        const placedOrdersElement = document.getElementById('placed-orders-metric');
        if (placedOrdersElement) {
            placedOrdersElement.textContent = metrics.placed_orders_count;
        }
        
        const cancelledOrdersElement = document.getElementById('cancelled-orders-metric');
        if (cancelledOrdersElement) {
            cancelledOrdersElement.textContent = metrics.cancelled_orders_count;
        }
        
        const filledOrdersElement = document.getElementById('filled-orders-metric');
        if (filledOrdersElement) {
            filledOrdersElement.textContent = metrics.filled_orders_count;
        }
        
        // Update recent actions log
        const actionsListElement = document.getElementById('recent-actions-list');
        if (actionsListElement && data.reconciliation_log) {
            if (data.reconciliation_log.length > 0) {
                actionsListElement.innerHTML = data.reconciliation_log.map(log => {
                    const time = new Date(log.timestamp).toLocaleString('en-AU', {
                        timeZone: 'Australia/Melbourne',
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit'
                    });
                    
                    let actionClass = 'action-info';
                    if (log.action.includes('cancelled')) {
                        actionClass = 'action-warning';
                    } else if (log.action.includes('matched') || log.action.includes('added')) {
                        actionClass = 'action-success';
                    }
                    
                    return `
                        <div class="action-item ${actionClass}" style="padding: 10px; margin-bottom: 8px; border-left: 3px solid rgba(255,255,255,0.2); background: rgba(255,255,255,0.02);">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                                <span class="label uppercase">${log.action.replace(/_/g, ' ')}</span>
                                <span class="label" style="color: var(--white-muted);">${time}</span>
                            </div>
                            <div style="font-size: 0.9rem; color: var(--white-muted);">
                                ${log.details.message || JSON.stringify(log.details)}
                            </div>
                            ${log.details.symbol ? `<div class="label" style="margin-top: 5px;">Symbol: ${log.details.symbol}</div>` : ''}
                        </div>
                    `;
                }).join('');
            } else {
                actionsListElement.innerHTML = '<div class="no-data">No recent actions</div>';
            }
        }
    } catch (error) {
        console.error('Error updating metrics:', error);
    }
}

// Fetch and update portfolio chart
async function updatePortfolioChart() {
    try {
        if (!portfolioSeries) return;
        
        const response = await fetch('/api/portfolio-history');
        
        // Check for HTTP errors
        if (!response.ok) {
            console.error(`Failed to fetch portfolio history: ${response.status}`);
            return;
        }
        
        const data = await response.json();
        
        if (!data.history || data.history.length === 0) {
            return;
        }
        
        // Transform data for LightweightCharts with validation
        const chartData = data.history
            .filter(point => point && point.timestamp && point.total_balance != null)
            .map(point => {
                // Parse ISO timestamp to Unix timestamp
                const timestamp = Math.floor(new Date(point.timestamp).getTime() / 1000);
                return {
                    time: timestamp,
                    value: point.total_balance
                };
            });
        
        // Sort by time (ascending)
        chartData.sort((a, b) => a.time - b.time);
        
        // Update the chart
        portfolioSeries.setData(chartData);
    } catch (error) {
        console.error('Error updating portfolio chart:', error);
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

// Time constants for duration calculations
const MS_PER_MINUTE = 60000;
const MS_PER_HOUR = 3600000;
const MS_PER_DAY = 86400000;

// Calculate duration from entry time to now
function calculateDuration(entryTime) {
    if (!entryTime || (typeof entryTime === 'string' && entryTime.trim() === '')) {
        return '-';
    }
    
    try {
        const entryDate = new Date(entryTime);
        // Check if date is valid
        if (isNaN(entryDate.getTime())) {
            return '-';
        }
        const now = new Date();
        const durationMs = now - entryDate;
        
        const days = Math.floor(durationMs / MS_PER_DAY);
        const hours = Math.floor((durationMs % MS_PER_DAY) / MS_PER_HOUR);
        const minutes = Math.floor((durationMs % MS_PER_HOUR) / MS_PER_MINUTE);
        
        if (days > 0) {
            return `${days}d ${hours}h`;
        } else if (hours > 0) {
            return `${hours}h ${minutes}m`;
        } else {
            return `${minutes}m`;
        }
    } catch (e) {
        return '-';
    }
}

// Fetch and update positions with TP/SL info
async function updatePositions() {
    try {
        const response = await fetch('/api/positions');
        const data = await response.json();
        
        const tbody = document.getElementById('positions-tbody');
        
        if (data.positions && data.positions.length > 0) {
            tbody.innerHTML = data.positions.map(pos => {
                const duration = calculateDuration(pos.entry_time);
                return `
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
                    <td>${duration}</td>
                    <td>${pos.take_profit ? '$' + pos.take_profit.toFixed(2) : '-'}</td>
                    <td>${pos.stop_loss ? '$' + pos.stop_loss.toFixed(2) : '-'}</td>
                </tr>
            `;
            }).join('');
        } else {
            tbody.innerHTML = '<tr><td colspan="10" class="no-data">No active positions</td></tr>';
        }
    } catch (error) {
        console.error('Error updating positions:', error);
    }
}

// Fetch and update pending orders
async function updatePendingOrders() {
    try {
        const response = await fetch('/api/pending-orders');
        const data = await response.json();
        
        const tbody = document.getElementById('pending-orders-tbody');
        
        // Combine bot-tracked pending orders and actual exchange orders
        const allOrders = [];
        // Use Set for O(1) duplicate checking
        const botTrackedOrderIds = new Set();
        
        // Add bot-tracked pending orders (for TP/SL tracking)
        if (data.pending_orders && Object.keys(data.pending_orders).length > 0) {
            Object.entries(data.pending_orders).forEach(([symbol, order]) => {
                const params = order.params || {};
                const orderId = order.order_id || '';
                botTrackedOrderIds.add(orderId);
                allOrders.push({
                    symbol: symbol,
                    side: (params.side || '').toUpperCase(),
                    price: params.entry_price || 0,
                    amount: params.quantity || 0,
                    take_profit: params.take_profit || 0,
                    stop_loss: params.stop_loss || 0,
                    order_id: orderId,
                    timestamp: order.timestamp || '',
                    source: 'bot_tracked',
                    type: 'limit'
                });
            });
        }
        
        // Add actual exchange open orders (these are the real orders on exchange)
        if (data.exchange_open_orders && data.exchange_open_orders.length > 0) {
            data.exchange_open_orders.forEach(order => {
                // Check if this order is already in bot-tracked (avoid duplicates) using Set for O(1) lookup
                if (!botTrackedOrderIds.has(order.order_id)) {
                    allOrders.push({
                        symbol: order.symbol || '',
                        side: (order.side || '').toUpperCase(),
                        price: order.price || order.stop_price || 0,
                        amount: order.amount || 0,
                        take_profit: null,
                        stop_loss: null,
                        order_id: order.order_id || '',
                        timestamp: order.timestamp || '',
                        source: 'exchange',
                        type: order.type || 'limit',
                        reduce_only: order.reduce_only || false,
                        stop_price: order.stop_price || null
                    });
                }
            });
        }
        
        if (allOrders.length > 0) {
            tbody.innerHTML = allOrders.map(order => {
                // Convert to Melbourne time
                let time = '-';
                if (order.timestamp) {
                    time = new Date(order.timestamp).toLocaleString('en-AU', { 
                        timeZone: 'Australia/Melbourne',
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit'
                    });
                }
                
                const side = order.side || '-';
                const entryPrice = order.price ? `$${Number(order.price).toFixed(2)}` : '-';
                const size = order.amount ? Number(order.amount).toFixed(4) : '-';
                const takeProfit = order.take_profit ? `$${Number(order.take_profit).toFixed(2)}` : '-';
                const stopLoss = order.stop_loss ? `$${Number(order.stop_loss).toFixed(2)}` : '-';
                const orderId = order.order_id ? order.order_id.toString().substring(0, 8) + '...' : '-';
                
                // Add type indicator for different order types
                let typeIndicator = '';
                if (order.type === 'STOP_MARKET' || order.type === 'stop_market') {
                    typeIndicator = ' (SL)';
                } else if (order.type === 'TAKE_PROFIT_MARKET' || order.type === 'take_profit_market') {
                    typeIndicator = ' (TP)';
                } else if (order.reduce_only) {
                    typeIndicator = ' (Close)';
                }
                
                // Source indicator
                const sourceClass = order.source === 'exchange' ? 'style="background: rgba(74, 222, 128, 0.1);"' : '';
                
                return `
                    <tr ${sourceClass}>
                        <td><strong>${order.symbol}</strong></td>
                        <td class="${side === 'BUY' ? 'positive' : side === 'SELL' ? 'negative' : ''}">${side}${typeIndicator}</td>
                        <td>${entryPrice}</td>
                        <td>${size}</td>
                        <td>${takeProfit}</td>
                        <td>${stopLoss}</td>
                        <td><span class="label" style="font-family: monospace;">${orderId}</span></td>
                        <td>${time}</td>
                    </tr>
                `;
            }).join('');
        } else {
            tbody.innerHTML = '<tr><td colspan="8" class="no-data">No pending orders</td></tr>';
        }
    } catch (error) {
        console.error('Error updating pending orders:', error);
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
            const winRateElement = document.getElementById('win-rate');
            if (winRateElement) {
                winRateElement.textContent = `${winRate}%`;
                winRateElement.className = winRate >= 50 ? 'stat-val value text-green' : 'stat-val value text-red';
            }
            
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
            const winRateElement = document.getElementById('win-rate');
            if (winRateElement) {
                winRateElement.textContent = '0%';
            }
        }
    } catch (error) {
        console.error('Error updating trades:', error);
    }
}

// Helper function to validate pending order object
function isPendingOrderValid(pendingOrder) {
    return pendingOrder && 
           typeof pendingOrder === 'object' && 
           Object.keys(pendingOrder).length > 0 &&
           pendingOrder.params &&
           typeof pendingOrder.params === 'object';
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
            const labelElement = document.getElementById(`info-${symbolKey}-label`);
            
            if (infoElement && data.order_blocks) {
                const bullishOBs = data.order_blocks.filter(ob => ob.type === 'bullish');
                const bearishOBs = data.order_blocks.filter(ob => ob.type === 'bearish');
                
                limitOrdersCount += bullishOBs.length + bearishOBs.length;
                
                let infoHTML = '';
                let labelHTML = '';
                
                // Check if there's a valid pending order for this specific symbol
                // Note: data.pending_order is fetched per-symbol from backend
                const hasPendingOrder = isPendingOrderValid(data.pending_order);
                
                // Helper function for distance formatting
                const formatDistance = (distancePct) => {
                    const sign = distancePct > 0 ? '+' : '';
                    const color = distancePct > 0 ? 'var(--signal-green)' : 'var(--signal-red)';
                    return { sign, color };
                };
                
                // Show bullish order blocks with distance
                if (bullishOBs.length > 0) {
                    bullishOBs.forEach((ob, index) => {
                        const { sign, color } = formatDistance(ob.distance_pct);
                        const orderIndicator = hasPendingOrder ? '📋 ' : '';
                        
                        infoHTML += `<div class="ob-info bullish">
                            🟢 ${orderIndicator}Bullish OB @ $${ob.entry_price ? ob.entry_price.toFixed(2) : 'N/A'}
                            <span style="color: ${color}; margin-left: 8px; font-weight: 500;">
                                ${sign}${ob.distance_pct}%
                            </span>
                        </div>`;
                        
                        // Update label with closest OB
                        if (index === 0) {
                            const absDistance = Math.abs(ob.distance_pct);
                            labelHTML = hasPendingOrder 
                                ? `📋 Order placed • ${absDistance.toFixed(1)}% away`
                                : `${absDistance.toFixed(1)}% to entry`;
                        }
                    });
                }
                
                // Show bearish order blocks with distance
                if (bearishOBs.length > 0) {
                    bearishOBs.forEach((ob, index) => {
                        const { sign, color } = formatDistance(ob.distance_pct);
                        const orderIndicator = hasPendingOrder ? '📋 ' : '';
                        
                        infoHTML += `<div class="ob-info bearish">
                            🔴 ${orderIndicator}Bearish OB @ $${ob.entry_price ? ob.entry_price.toFixed(2) : 'N/A'}
                            <span style="color: ${color}; margin-left: 8px; font-weight: 500;">
                                ${sign}${ob.distance_pct}%
                            </span>
                        </div>`;
                        
                        // Update label with closest OB if no bullish OB
                        if (index === 0 && bullishOBs.length === 0) {
                            const absDistance = Math.abs(ob.distance_pct);
                            labelHTML = hasPendingOrder 
                                ? `📋 Order placed • ${absDistance.toFixed(1)}% away`
                                : `${absDistance.toFixed(1)}% to entry`;
                        }
                    });
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
                
                // Show pending order info if exists
                if (hasPendingOrder) {
                    const params = data.pending_order.params;
                    infoHTML += `<div class="ob-info" style="background: rgba(255,255,255,0.05);">
                        📋 Limit Order: ${params.side ? params.side.toUpperCase() : 'N/A'} @ $${params.entry_price ? params.entry_price.toFixed(2) : 'N/A'}
                    </div>`;
                }
                
                infoElement.innerHTML = infoHTML || '<div class="no-data">No order blocks detected</div>';
                
                // Update label
                if (labelElement) {
                    labelElement.innerHTML = labelHTML || 'Scanning...';
                }
                
                // Draw order blocks and markers on chart
                drawOrderBlocks(symbolKey, data.order_blocks, data.position);
            }
        }
        
        // Update limit orders count
        const limitOrdersElement = document.getElementById('limit-orders-count');
        if (limitOrdersElement) {
            limitOrdersElement.textContent = limitOrdersCount;
        }
        
    } catch (error) {
        console.error('Error updating market data:', error);
    }
}

/**
 * Calculate percentage difference between two prices
 * @param {number} fromPrice - Starting price (entry)
 * @param {number} toPrice - Target price (TP or SL)
 * @returns {string} - Formatted percentage string (e.g., "+2.5" or "-1.2")
 */
function calculatePercentageChange(fromPrice, toPrice) {
    if (!fromPrice || fromPrice === 0) return "0.0";
    const change = ((toPrice - fromPrice) / fromPrice) * 100;
    return change.toFixed(1);
}

/**
 * Format price with proper decimal places and commas
 * @param {number} price - Price value
 * @returns {string} - Formatted price string
 */
function formatPrice(price) {
    if (price == null) return "0.00";
    return price.toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
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
    
    // Draw OB ZONES - Using prominent boundary lines to define the zone
    // Note: LightweightCharts v4.1.1 doesn't have native rectangle primitives
    // The dashed boundary lines with clear labels provide strong visual definition
    orderBlocks.forEach(ob => {
        if (!ob.time || !ob.ob_top || !ob.ob_bottom) return;
        
        // Draw boundary lines (dashed) - These clearly define the OB zone
        const boundaryColor = ob.type === 'bullish' ? '#4ADE80' : '#F43F5E';
        
        // Top boundary - entry level for bullish, top of zone for bearish
        series.createPriceLine({
            price: ob.ob_top,
            color: boundaryColor,
            lineWidth: 2, // Increased thickness for better visibility
            lineStyle: 2, // Dashed
            axisLabelVisible: true,
            title: ob.type === 'bullish' 
                ? `🟢 OB Entry $${formatPrice(ob.ob_top)}`
                : `🔴 OB Top $${formatPrice(ob.ob_top)}`,
        });
        
        // Bottom boundary - bottom of zone for bullish, entry level for bearish
        series.createPriceLine({
            price: ob.ob_bottom,
            color: boundaryColor,
            lineWidth: 2, // Increased thickness for better visibility
            lineStyle: 2, // Dashed
            axisLabelVisible: true,
            title: ob.type === 'bullish'
                ? `🟢 OB Bottom $${formatPrice(ob.ob_bottom)}`
                : `🔴 OB Entry $${formatPrice(ob.ob_bottom)}`,
        });
        
        // Add formation marker arrow
        markers.push({
            time: ob.time,
            position: ob.type === 'bullish' ? 'belowBar' : 'aboveBar',
            color: boundaryColor,
            shape: ob.type === 'bullish' ? 'arrowUp' : 'arrowDown',
            text: `${ob.type === 'bullish' ? '🟢' : '🔴'} OB`,
            size: 1
        });
    });
    
    // Draw POSITION LINES (Entry, TP, SL) - if position exists
    if (position && position.entry_price) {
        const entryPrice = position.entry_price;
        
        // ENTRY LINE - Most prominent, cyan color
        series.createPriceLine({
            price: entryPrice,
            color: '#00D9FF', // Bright cyan
            lineWidth: 3,
            lineStyle: 0, // Solid
            axisLabelVisible: true,
            title: `🎯 ENTRY $${formatPrice(entryPrice)}`,
        });
        
        // TAKE PROFIT LINE
        if (position.take_profit) {
            const tpPrice = position.take_profit;
            const tpPercent = calculatePercentageChange(entryPrice, tpPrice);
            
            series.createPriceLine({
                price: tpPrice,
                color: '#4ADE80', // Bright green
                lineWidth: 3,
                lineStyle: 0,
                axisLabelVisible: true,
                title: `✅ TP $${formatPrice(tpPrice)} (+${tpPercent}%)`,
            });
        }
        
        // STOP LOSS LINE
        if (position.stop_loss) {
            const slPrice = position.stop_loss;
            const slPercent = calculatePercentageChange(entryPrice, slPrice);
            
            series.createPriceLine({
                price: slPrice,
                color: '#F43F5E', // Bright red
                lineWidth: 3,
                lineStyle: 0,
                axisLabelVisible: true,
                title: `❌ SL $${formatPrice(slPrice)} (${slPercent}%)`,
            });
        }
    }
    
    // Apply markers
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
        updatePendingOrders(),
        updateTrades(),
        updateMarketData(),
        updateMetrics(),
        updatePortfolioChart()
    ]);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    console.log('HunterZ Trading System - Initializing...');
    
    // Initialize charts
    initializeCharts();
    initializePortfolioChart();
    
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

// ========================================
// 3D PARTICLE CANVAS BACKGROUND
// ========================================
const canvas = document.getElementById('bg-canvas');
if (canvas) {
    const ctx = canvas.getContext('2d');

    let width, height;
    let particles = [];
    const PARTICLE_COUNT = 3000;

    function resize() {
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
    }

    window.addEventListener('resize', resize);
    resize();

    class Point {
        constructor() {
            this.reset();
        }

        reset() {
            this.theta = Math.random() * Math.PI * 2;
            this.phi = Math.random() * Math.PI;
            this.baseRadius = (Math.random() * 500) + 900; 
            this.x = 0;
            this.y = 0;
            this.z = 0;
            this.size = Math.random() * 1.5;
        }

        update(time) {
            // Reduced multiplier for gentler waves
            let wave1 = Math.sin(this.theta * 3 + time * 0.5) * 30; 
            let wave2 = Math.cos(this.phi * 2 + time * 0.3) * 30;

            let currentRadius = this.baseRadius + wave1 + wave2;

            this.x = currentRadius * Math.sin(this.phi) * Math.cos(this.theta);
            this.y = currentRadius * Math.sin(this.phi) * Math.sin(this.theta);
            this.z = currentRadius * Math.cos(this.phi);
        }
    }

    for (let i = 0; i < PARTICLE_COUNT; i++) {
        particles.push(new Point());
    }

    let time = 0;

    function animate() {
        ctx.clearRect(0, 0, width, height);
        
        // SIGNIFICANTLY SLOWED DOWN
        time += 0.0008; 

        const cx = width / 2;
        const cy = height / 2;

        // Very slow rotation
        let rotX = time * 0.1;
        let rotY = time * 0.12;

        ctx.fillStyle = '#FFFFFF';

        particles.forEach(p => {
            p.update(time);

            let x = p.x;
            let y = p.y;
            let z = p.z;

            let x1 = x * Math.cos(rotY) - z * Math.sin(rotY);
            let z1 = x * Math.sin(rotY) + z * Math.cos(rotY);

            let y2 = y * Math.cos(rotX) - z1 * Math.sin(rotX);
            let z2 = y * Math.sin(rotX) + z1 * Math.cos(rotX);

            let fov = 1200; 
            let scale = fov / (fov + z2); 
            let x2d = cx + x1 * scale;
            let y2d = cy + y2 * scale;

            if (scale > 0) {
                let alpha = Math.max(0, (scale - 0.2) * 0.5);
                ctx.globalAlpha = alpha;
                ctx.beginPath();
                ctx.arc(x2d, y2d, p.size * scale, 0, Math.PI * 2);
                ctx.fill();
            }
        });

        requestAnimationFrame(animate);
    }

    animate();
}
