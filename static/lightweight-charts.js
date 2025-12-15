// Mock LightweightCharts for testing when CDN is blocked
// This is a minimal implementation for demonstration purposes
// In production, use the full library from CDN

(function() {
    'use strict';
    
    window.LightweightCharts = {
        CrosshairMode: {
            Normal: 0
        },
        
        createChart: function(container, options) {
            // Create mock canvas
            const canvas = document.createElement('canvas');
            canvas.width = options.width || 600;
            canvas.height = options.height || 300;
            canvas.style.width = '100%';
            canvas.style.height = '100%';
            canvas.style.borderRadius = '12px';
            container.innerHTML = '';
            container.appendChild(canvas);
            
            const ctx = canvas.getContext('2d');
            
            // Draw a simple gradient background
            const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height);
            gradient.addColorStop(0, 'rgba(59, 130, 246, 0.05)');
            gradient.addColorStop(1, 'rgba(139, 92, 246, 0.05)');
            ctx.fillStyle = gradient;
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            
            // Draw text
            ctx.fillStyle = '#94a3b8';
            ctx.font = '14px -apple-system, BlinkMacSystemFont, Inter, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('📈 Chart Ready - Waiting for Live Data', canvas.width / 2, canvas.height / 2 - 10);
            ctx.font = '12px -apple-system, BlinkMacSystemFont, Inter, sans-serif';
            ctx.fillText('Charts will display when market data is available', canvas.width / 2, canvas.height / 2 + 10);
            
            return {
                addCandlestickSeries: function() {
                    return {
                        setData: function(data) {
                            // In a real implementation, this would draw the candlesticks
                            if (data && data.length > 0) {
                                ctx.clearRect(0, 0, canvas.width, canvas.height);
                                ctx.fillStyle = gradient;
                                ctx.fillRect(0, 0, canvas.width, canvas.height);
                                
                                ctx.fillStyle = '#1e3a8a';
                                ctx.font = '14px -apple-system, BlinkMacSystemFont, Inter, sans-serif';
                                ctx.textAlign = 'center';
                                ctx.fillText(`📊 ${data.length} candles loaded`, canvas.width / 2, canvas.height / 2);
                            }
                        },
                        setMarkers: function(markers) {
                            // Mock marker setting
                        },
                        createPriceLine: function(options) {
                            // Mock price line
                            return {};
                        }
                    };
                },
                addLineSeries: function() {
                    return {
                        setData: function() {},
                        createPriceLine: function() { return {}; }
                    };
                },
                addAreaSeries: function() {
                    return {
                        setData: function() {},
                        createPriceLine: function() { return {}; }
                    };
                },
                applyOptions: function(options) {
                    if (options.width) {
                        canvas.width = options.width;
                        canvas.style.width = '100%';
                    }
                },
                resize: function() {
                    // Handle resize
                },
                removeSeries: function(series) {
                    // Mock series removal
                }
            };
        }
    };
})();
