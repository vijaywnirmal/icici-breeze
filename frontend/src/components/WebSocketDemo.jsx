import React, { useEffect, useRef, useState } from 'react'

const WebSocketDemo = () => {
    const [instruments, setInstruments] = useState([])
    const [selectedInstruments, setSelectedInstruments] = useState([])
    const [wsConnected, setWsConnected] = useState(false)
    const [tickData, setTickData] = useState({})
    const [loading, setLoading] = useState(false)
    
    const wsRef = useRef(null)
    const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

    // Fetch all WebSocket-enabled instruments
    const fetchInstruments = async () => {
        try {
            setLoading(true)
            const response = await fetch(`${apiBase}/api/instruments/websocket-enabled?exchange=NSE&limit=100`)
            const data = await response.json()
            
            if (data.success) {
                setInstruments(data.instruments || [])
                console.log(`Found ${data.count} WebSocket-enabled instruments`)
            }
        } catch (error) {
            console.error('Error fetching instruments:', error)
        } finally {
            setLoading(false)
        }
    }

    // Connect to WebSocket
    const connectWebSocket = () => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            return
        }

        const wsUrl = apiBase.replace('http', 'ws') + '/ws/stocks'
        const ws = new WebSocket(wsUrl)
        wsRef.current = ws

        ws.onopen = () => {
            console.log('WebSocket connected')
            setWsConnected(true)
        }

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data)
                if (data.type === 'tick') {
                    setTickData(prev => ({
                        ...prev,
                        [data.symbol]: {
                            ltp: data.ltp,
                            close: data.close,
                            change_pct: data.change_pct,
                            timestamp: data.timestamp
                        }
                    }))
                }
            } catch (error) {
                console.error('Error parsing WebSocket message:', error)
            }
        }

        ws.onclose = () => {
            console.log('WebSocket disconnected')
            setWsConnected(false)
        }

        ws.onerror = (error) => {
            console.error('WebSocket error:', error)
            setWsConnected(false)
        }
    }

    // Subscribe to selected instruments
    const subscribeToInstruments = () => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
            console.error('WebSocket not connected')
            return
        }

        if (selectedInstruments.length === 0) {
            console.log('No instruments selected')
            return
        }

        // Format instruments for WebSocket subscription
        const symbols = selectedInstruments.map(inst => ({
            stock_code: inst.symbol,
            exchange_code: inst.exchange_code || 'NSE',
            product_type: 'cash',
            token: inst.token
        }))

        // Send subscription message
        wsRef.current.send(JSON.stringify({
            action: 'subscribe_many',
            symbols: symbols
        }))

        console.log(`Subscribed to ${selectedInstruments.length} instruments`)
    }

    // Toggle instrument selection
    const toggleInstrument = (instrument) => {
        setSelectedInstruments(prev => {
            const exists = prev.find(inst => inst.symbol === instrument.symbol)
            if (exists) {
                return prev.filter(inst => inst.symbol !== instrument.symbol)
            } else {
                return [...prev, instrument]
            }
        })
    }

    useEffect(() => {
        fetchInstruments()
        
        return () => {
            if (wsRef.current) {
                wsRef.current.close()
            }
        }
    }, [])

    return (
        <div style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto' }}>
            <h2>WebSocket Plug-and-Play Demo</h2>
            
            {/* Connection Status */}
            <div style={{ marginBottom: '20px' }}>
                <button 
                    onClick={connectWebSocket}
                    disabled={wsConnected}
                    style={{
                        padding: '10px 20px',
                        backgroundColor: wsConnected ? '#4CAF50' : '#2196F3',
                        color: 'white',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: wsConnected ? 'default' : 'pointer'
                    }}
                >
                    {wsConnected ? 'Connected' : 'Connect WebSocket'}
                </button>
                
                <span style={{ marginLeft: '10px' }}>
                    Status: {wsConnected ? '🟢 Connected' : '🔴 Disconnected'}
                </span>
            </div>

            {/* Instrument Selection */}
            <div style={{ marginBottom: '20px' }}>
                <h3>Select Instruments ({selectedInstruments.length} selected)</h3>
                <button 
                    onClick={subscribeToInstruments}
                    disabled={!wsConnected || selectedInstruments.length === 0}
                    style={{
                        padding: '10px 20px',
                        backgroundColor: '#FF9800',
                        color: 'white',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        marginBottom: '10px'
                    }}
                >
                    Subscribe to Selected ({selectedInstruments.length})
                </button>
                
                {loading ? (
                    <div>Loading instruments...</div>
                ) : (
                    <div style={{ 
                        display: 'grid', 
                        gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', 
                        gap: '10px',
                        maxHeight: '400px',
                        overflowY: 'auto'
                    }}>
                        {instruments.map((instrument, index) => (
                            <div 
                                key={index}
                                onClick={() => toggleInstrument(instrument)}
                                style={{
                                    padding: '10px',
                                    border: '1px solid #ddd',
                                    borderRadius: '4px',
                                    cursor: 'pointer',
                                    backgroundColor: selectedInstruments.find(inst => inst.symbol === instrument.symbol) ? '#E3F2FD' : 'white'
                                }}
                            >
                                <div><strong>{instrument.symbol}</strong></div>
                                <div style={{ fontSize: '14px', color: '#666' }}>
                                    {instrument.company_name}
                                </div>
                                <div style={{ fontSize: '12px', color: '#999' }}>
                                    Token: {instrument.token}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Live Tick Data */}
            <div>
                <h3>Live Tick Data</h3>
                <div style={{ 
                    display: 'grid', 
                    gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', 
                    gap: '10px'
                }}>
                    {Object.entries(tickData).map(([symbol, data]) => (
                        <div 
                            key={symbol}
                            style={{
                                padding: '10px',
                                border: '1px solid #ddd',
                                borderRadius: '4px',
                                backgroundColor: '#f9f9f9'
                            }}
                        >
                            <div><strong>{symbol}</strong></div>
                            <div>LTP: {data.ltp || '--'}</div>
                            <div>Close: {data.close || '--'}</div>
                            <div>Change: {data.change_pct || '--'}%</div>
                            <div style={{ fontSize: '12px', color: '#666' }}>
                                {data.timestamp ? new Date(data.timestamp).toLocaleTimeString() : '--'}
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    )
}

export default WebSocketDemo
