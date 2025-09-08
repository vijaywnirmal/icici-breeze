import React, { useState, useEffect, useRef, useCallback } from 'react'

export default function StockSearch() {
	const [searchQuery, setSearchQuery] = useState('')
	const [searchResults, setSearchResults] = useState([])
	const [selectedStocks, setSelectedStocks] = useState([])
	const [marketStatus, setMarketStatus] = useState(null)
	const [loading, setLoading] = useState(false)
	const [error, setError] = useState('')
	const [wsConnection, setWsConnection] = useState(null)
	const [livePrices, setLivePrices] = useState({})
	const searchTimeoutRef = useRef(null)
	const dragItemRef = useRef(null)
	const dragOverItemRef = useRef(null)

	const apiBase = import.meta.env.VITE_API_BASE_URL || ''
	const wsBase = apiBase.replace('http', 'ws')

	// Check market status on component mount
	useEffect(() => {
		checkMarketStatus()
	}, [])

	// WebSocket connection for live prices
	useEffect(() => {
		if (marketStatus?.is_open && selectedStocks.length > 0) {
			connectWebSocket()
		} else {
			disconnectWebSocket()
		}

		return () => {
			disconnectWebSocket()
		}
	}, [marketStatus?.is_open, selectedStocks])

	// Subscribe to new stocks when they're added
	useEffect(() => {
		if (wsConnection && wsConnection.readyState === WebSocket.OPEN && selectedStocks.length > 0) {
			const latestStock = selectedStocks[selectedStocks.length - 1]
			wsConnection.send(JSON.stringify({
				action: 'subscribe',
				symbol: latestStock.symbol || '',
				exchange_code: latestStock.exchange || 'NSE',
				product_type: 'cash'
			}))
		}
	}, [selectedStocks.length, wsConnection])

	const checkMarketStatus = async () => {
		try {
			const response = await fetch(`${apiBase}/api/market/status`)
			const data = await response.json()
			if (data.success) {
				setMarketStatus(data)
			}
		} catch (err) {
			console.error('Failed to check market status:', err)
		}
	}

	const searchStocks = useCallback(async (query) => {
		if (!query || query.length < 2) {
			setSearchResults([])
			return
		}

		setLoading(true)
		setError('')
		
		try {
			// Use the new Live Trading endpoint that only returns WebSocket-enabled instruments
			const response = await fetch(`${apiBase}/api/instruments/live-trading?q=${encodeURIComponent(query)}&limit=20`)
			const data = await response.json()
			
			if (data.success) {
				setSearchResults(data.items || [])
			} else {
				setError(data.error || 'Search failed')
				setSearchResults([])
			}
		} catch (err) {
			setError('Failed to search stocks')
			setSearchResults([])
		} finally {
			setLoading(false)
		}
	}, [apiBase])

	// Debounced search
	useEffect(() => {
		if (searchTimeoutRef.current) {
			clearTimeout(searchTimeoutRef.current)
		}

		searchTimeoutRef.current = setTimeout(() => {
			searchStocks(searchQuery)
		}, 300)

		return () => {
			if (searchTimeoutRef.current) {
				clearTimeout(searchTimeoutRef.current)
			}
		}
	}, [searchQuery, searchStocks])

	const connectWebSocket = () => {
		if (wsConnection) {
			wsConnection.close()
		}

		const ws = new WebSocket(`${wsBase}/ws/stocks`)
		setWsConnection(ws)

		ws.onopen = () => {
			console.log('WebSocket connected')
			// Subscribe to all selected stocks
			selectedStocks.forEach(stock => {
				ws.send(JSON.stringify({
					action: 'subscribe',
					symbol: stock.symbol || '',
					exchange_code: stock.exchange || 'NSE',
					product_type: 'cash'
				}))
			})
		}

		ws.onmessage = (event) => {
			try {
				const data = JSON.parse(event.data)
				if (data.type === 'tick' && data.symbol) {
					setLivePrices(prev => ({
						...prev,
						[data.symbol]: {
							ltp: data.ltp,
							change_pct: data.change_pct,
							bid: data.bid,
							ask: data.ask,
							timestamp: data.timestamp
						}
					}))
				}
			} catch (err) {
				console.error('Failed to parse WebSocket message:', err)
			}
		}

		ws.onerror = (error) => {
			console.error('WebSocket error:', error)
		}

		ws.onclose = () => {
			console.log('WebSocket disconnected')
		}
	}

	const disconnectWebSocket = () => {
		if (wsConnection) {
			wsConnection.close()
			setWsConnection(null)
		}
	}

	const addStock = (stock) => {
		if (!selectedStocks.find(s => s.symbol === stock.symbol)) {
			const newStock = {
				...stock,
				id: `${stock.symbol}_${Date.now()}`
			}
			setSelectedStocks(prev => [...prev, newStock])
			setSearchQuery('')
			setSearchResults([])
		}
	}

	const removeStock = (stockId) => {
		setSelectedStocks(prev => {
			const stockToRemove = prev.find(s => s.id === stockId)
			if (stockToRemove && wsConnection && wsConnection.readyState === WebSocket.OPEN) {
				// Unsubscribe from the stock
				wsConnection.send(JSON.stringify({
					action: 'unsubscribe',
					symbol: stockToRemove.symbol || '',
					exchange_code: stockToRemove.exchange || 'NSE',
					product_type: 'cash'
				}))
			}
			return prev.filter(s => s.id !== stockId)
		})
	}

	const handleDragStart = (e, stock) => {
		dragItemRef.current = stock
		e.dataTransfer.effectAllowed = 'move'
		e.dataTransfer.setData('text/html', e.target.outerHTML)
	}

	const handleDragOver = (e) => {
		e.preventDefault()
		e.dataTransfer.dropEffect = 'move'
	}

	const handleDrop = (e) => {
		e.preventDefault()
		if (dragItemRef.current) {
			addStock(dragItemRef.current)
			dragItemRef.current = null
		}
	}

	const formatPrice = (price) => {
		if (typeof price !== 'number') return '--'
		return price.toFixed(2)
	}

	const formatChange = (change) => {
		if (typeof change !== 'number') return '--'
		const sign = change >= 0 ? '+' : ''
		return `${sign}${change.toFixed(2)}%`
	}

	const getChangeColor = (change) => {
		if (typeof change !== 'number') return 'var(--muted)'
		return change >= 0 ? '#57d38c' : '#ff5c5c'
	}

	return (
		<div className="stock-search-container">
			<div className="search-section">
				<h2 style={{ color: 'var(--text)', marginBottom: '20px' }}>Stock Search & Live Prices</h2>
				
				{/* Market Status */}
				<div className="market-status" style={{ marginBottom: '15px' }}>
					<span 
						className={`status-indicator ${marketStatus?.is_open ? 'open' : 'closed'}`}
						style={{
							padding: '8px 16px',
							borderRadius: '20px',
							fontWeight: 'bold',
							fontSize: '14px',
							backgroundColor: marketStatus?.is_open ? 'rgba(87, 211, 140, 0.2)' : 'rgba(255, 92, 92, 0.2)',
							color: marketStatus?.is_open ? '#57d38c' : '#ff5c5c',
							border: `1px solid ${marketStatus?.is_open ? 'rgba(87, 211, 140, 0.3)' : 'rgba(255, 92, 92, 0.3)'}`
						}}
					>
						{marketStatus?.is_open ? '🟢 Market Open' : '🔴 Market Closed'}
					</span>
				</div>

				{/* Search Input */}
				<div className="search-input-container" style={{ position: 'relative', marginBottom: '15px' }}>
					<input
						type="text"
						placeholder="Search stocks by symbol or company name..."
						value={searchQuery}
						onChange={(e) => setSearchQuery(e.target.value)}
						style={{
							width: '100%',
							padding: '12px 16px',
							border: '1px solid rgba(255,255,255,0.08)',
							borderRadius: '10px',
							backgroundColor: '#0f141d',
							color: 'var(--text)',
							fontSize: '16px',
							outline: 'none',
							transition: 'border-color 0.3s, box-shadow 0.3s'
						}}
						onFocus={(e) => {
							e.target.style.borderColor = 'var(--accent)'
							e.target.style.boxShadow = '0 0 0 3px rgba(79, 156, 255, 0.2)'
						}}
						onBlur={(e) => {
							e.target.style.borderColor = 'rgba(255,255,255,0.08)'
							e.target.style.boxShadow = 'none'
						}}
					/>
					{loading && (
						<div 
							className="loading-spinner" 
							style={{
								position: 'absolute',
								right: '12px',
								top: '50%',
								transform: 'translateY(-50%)',
								fontSize: '18px'
							}}
						>
							⏳
						</div>
					)}
				</div>

				{/* Search Results */}
				{searchResults.length > 0 && (
					<div 
						className="search-results"
						style={{
							border: '1px solid rgba(255,255,255,0.08)',
							borderRadius: '10px',
							backgroundColor: 'var(--panel)',
							maxHeight: '300px',
							overflowY: 'auto',
							marginBottom: '20px'
						}}
					>
						<h3 style={{ color: 'var(--text)', margin: '15px', fontSize: '16px' }}>Search Results</h3>
						<div className="results-list" style={{ padding: '10px' }}>
							{searchResults.map((stock) => (
								<div
									key={`${stock.symbol}_${stock.exchange}`}
									className="search-result-item"
									draggable
									onDragStart={(e) => handleDragStart(e, stock)}
									onClick={() => addStock(stock)}
									style={{
										display: 'flex',
										justifyContent: 'space-between',
										alignItems: 'center',
										padding: '12px',
										borderBottom: '1px solid rgba(255,255,255,0.06)',
										cursor: 'pointer',
										transition: 'background-color 0.2s',
										backgroundColor: 'transparent'
									}}
									onMouseEnter={(e) => {
										e.target.style.backgroundColor = 'rgba(255,255,255,0.06)'
									}}
									onMouseLeave={(e) => {
										e.target.style.backgroundColor = 'transparent'
									}}
								>
									<div className="stock-info" style={{ flex: 1 }}>
										<div 
											className="stock-symbol" 
											style={{ 
												fontWeight: 'bold', 
												fontSize: '16px', 
												color: 'var(--text)' 
											}}
										>
											{stock.symbol}
										</div>
										<div 
											className="stock-name" 
											style={{ 
												fontSize: '14px', 
												color: 'var(--muted)', 
												marginTop: '2px' 
											}}
										>
											{stock.company_name || stock.short_name}
										</div>
										<div 
											className="stock-exchange" 
											style={{ 
												fontSize: '12px', 
												color: 'var(--muted)', 
												marginTop: '2px' 
											}}
										>
											{stock.exchange}
										</div>
									</div>
									<div 
										className="add-button"
										style={{
											backgroundColor: 'var(--accent)',
											color: 'white',
											padding: '6px 12px',
											borderRadius: '6px',
											fontSize: '12px',
											fontWeight: 'bold',
											cursor: 'pointer'
										}}
									>
										+ Add
									</div>
								</div>
							))}
						</div>
					</div>
				)}

				{error && (
					<div 
						className="error-message"
						style={{
							color: 'var(--danger)',
							backgroundColor: 'rgba(255, 92, 92, 0.1)',
							border: '1px solid rgba(255, 92, 92, 0.2)',
							padding: '8px 12px',
							borderRadius: '6px',
							marginTop: '10px'
						}}
					>
						{error}
					</div>
				)}
			</div>

			{/* Selected Stocks with Live Prices */}
			<div className="selected-stocks-section">
				<h3 style={{ color: 'var(--text)', marginBottom: '15px' }}>
					Selected Stocks {marketStatus?.is_open && '(Live Prices)'}
				</h3>
				
				{selectedStocks.length === 0 ? (
					<div 
						className="drop-zone" 
						onDragOver={handleDragOver} 
						onDrop={handleDrop}
						style={{
							border: '2px dashed rgba(255,255,255,0.2)',
							borderRadius: '10px',
							padding: '40px',
							textAlign: 'center',
							color: 'var(--muted)',
							backgroundColor: 'rgba(255,255,255,0.03)'
						}}
					>
						<p>Drag and drop stocks here or click to add from search results</p>
					</div>
				) : (
					<div 
						className="selected-stocks-grid"
						style={{
							display: 'grid',
							gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
							gap: '20px'
						}}
					>
						{selectedStocks.map((stock) => {
							const liveData = livePrices[stock.symbol] || {}
							return (
								<div 
									key={stock.id} 
									className="stock-card"
									style={{
										border: '1px solid rgba(255,255,255,0.08)',
										borderRadius: '10px',
										padding: '16px',
										backgroundColor: 'var(--panel)',
										boxShadow: '0 4px 12px rgba(0,0,0,0.15)'
									}}
								>
									<div 
										className="stock-header"
										style={{
											display: 'flex',
											justifyContent: 'space-between',
											alignItems: 'center',
											marginBottom: '8px'
										}}
									>
										<div 
											className="stock-symbol"
											style={{ 
												fontWeight: 'bold', 
												fontSize: '18px', 
												color: 'var(--text)' 
											}}
										>
											{stock.symbol}
										</div>
										<button 
											className="remove-button"
											onClick={() => removeStock(stock.id)}
											title="Remove stock"
											style={{
												background: 'var(--danger)',
												color: 'white',
												border: 'none',
												borderRadius: '50%',
												width: '24px',
												height: '24px',
												cursor: 'pointer',
												fontSize: '16px',
												lineHeight: '1'
											}}
										>
											×
										</button>
									</div>
									<div 
										className="stock-name"
										style={{ 
											fontSize: '14px', 
											color: 'var(--muted)', 
											marginBottom: '4px' 
										}}
									>
										{stock.company_name || stock.short_name}
									</div>
									<div 
										className="stock-exchange"
										style={{ 
											fontSize: '12px', 
											color: 'var(--muted)', 
											marginBottom: '12px' 
										}}
									>
										{stock.exchange}
									</div>
									
									{marketStatus?.is_open ? (
										<div className="live-prices" style={{ marginTop: '12px' }}>
											<div 
												className="price-row"
												style={{
													display: 'flex',
													justifyContent: 'space-between',
													marginBottom: '4px'
												}}
											>
												<span 
													className="price-label"
													style={{ fontWeight: 'bold', color: 'var(--muted)' }}
												>
													LTP:
												</span>
												<span 
													className="price-value"
													style={{ fontWeight: 'bold', color: 'var(--text)' }}
												>
													₹{formatPrice(liveData.ltp)}
												</span>
											</div>
											<div 
												className="price-row"
												style={{
													display: 'flex',
													justifyContent: 'space-between',
													marginBottom: '4px'
												}}
											>
												<span 
													className="price-label"
													style={{ fontWeight: 'bold', color: 'var(--muted)' }}
												>
													Change:
												</span>
												<span 
													className="price-value"
													style={{ 
														fontWeight: 'bold',
														color: getChangeColor(liveData.change_pct)
													}}
												>
													{formatChange(liveData.change_pct)}
												</span>
											</div>
											{liveData.bid && liveData.ask && (
												<div 
													className="bid-ask"
													style={{
														marginTop: '8px',
														paddingTop: '8px',
														borderTop: '1px solid rgba(255,255,255,0.08)'
													}}
												>
													<div 
														className="bid-ask-row"
														style={{
															display: 'flex',
															justifyContent: 'space-between',
															fontSize: '12px',
															color: 'var(--muted)'
														}}
													>
														<span>Bid: ₹{formatPrice(liveData.bid)}</span>
														<span>Ask: ₹{formatPrice(liveData.ask)}</span>
													</div>
												</div>
											)}
										</div>
									) : (
										<div 
											className="market-closed"
											style={{
												textAlign: 'center',
												color: 'var(--muted)',
												marginTop: '12px',
												padding: '12px',
												backgroundColor: 'rgba(255,255,255,0.03)',
												borderRadius: '6px'
											}}
										>
											<p style={{ margin: '0 0 4px 0' }}>Market is closed</p>
											<p style={{ margin: '0' }}>Live prices unavailable</p>
										</div>
									)}
								</div>
							)
						})}
					</div>
				)}
			</div>

		</div>
	)
}
