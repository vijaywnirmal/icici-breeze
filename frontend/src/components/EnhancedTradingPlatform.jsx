import React, { useState, useEffect, useRef, useCallback } from 'react'

export default function EnhancedTradingPlatform() {
	const [searchQuery, setSearchQuery] = useState('')
	const [searchResults, setSearchResults] = useState([])
	const [watchlist, setWatchlist] = useState([])
	const [marketStatus, setMarketStatus] = useState(null)
	const [loading, setLoading] = useState(false)
	const [error, setError] = useState('')
	const [wsConnection, setWsConnection] = useState(null)
	const [livePrices, setLivePrices] = useState({})
	const [selectedTab, setSelectedTab] = useState('search') // 'search', 'watchlist', 'trending'
	const searchTimeoutRef = useRef(null)

	const apiBase = import.meta.env.VITE_API_BASE_URL || ''
	const wsBase = apiBase.replace('http', 'ws')

	// Check market status on component mount
	useEffect(() => {
		checkMarketStatus()
		loadWatchlist()
		// Seed cached prices for any previously saved symbols
		try {
			const saved = JSON.parse(localStorage.getItem('trading_watchlist') || '[]')
			if (Array.isArray(saved) && saved.length > 0) {
				const seeded = {}
				saved.forEach(item => {
					const cache = JSON.parse(localStorage.getItem(`ltp:${item.symbol}`) || 'null')
					if (cache && typeof cache === 'object') {
						seeded[item.symbol] = cache
					}
				})
				if (Object.keys(seeded).length > 0) {
					setLivePrices(prev => ({ ...seeded, ...prev }))
				}
			}
		} catch (_) {}
	}, [])

	// WebSocket connection for live prices
	useEffect(() => {
		if (marketStatus?.is_open && watchlist.length > 0) {
			connectWebSocket()
		} else {
			disconnectWebSocket()
		}

		return () => {
			disconnectWebSocket()
		}
	}, [marketStatus?.is_open, watchlist])

	// Subscribe to new stocks when they're added
	useEffect(() => {
		if (wsConnection && wsConnection.readyState === WebSocket.OPEN && watchlist.length > 0) {
			// Subscribe to all watchlist stocks
			watchlist.forEach(stock => {
				wsConnection.send(JSON.stringify({
					action: 'subscribe',
					symbol: stock.symbol || '',
					exchange_code: stock.exchange || 'NSE',
					product_type: 'cash'
				}))
			})
		}
	}, [watchlist.length, wsConnection])

	// Whenever the watchlist changes, seed price cache for newly added symbols
	useEffect(() => {
		try {
			if (!Array.isArray(watchlist) || watchlist.length === 0) return
			const seeded = {}
			watchlist.forEach(item => {
				const cache = JSON.parse(localStorage.getItem(`ltp:${item.symbol}`) || 'null')
				if (cache && typeof cache === 'object') {
					seeded[item.symbol] = cache
				}
			})
			if (Object.keys(seeded).length > 0) {
				setLivePrices(prev => ({ ...seeded, ...prev }))
			}
		} catch (_) {}
	}, [watchlist])

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

	const loadWatchlist = () => {
		try {
			const saved = localStorage.getItem('trading_watchlist')
			if (saved) {
				setWatchlist(JSON.parse(saved))
			}
		} catch (err) {
			console.error('Failed to load watchlist:', err)
		}
	}

	const saveWatchlist = (newWatchlist) => {
		try {
			localStorage.setItem('trading_watchlist', JSON.stringify(newWatchlist))
		} catch (err) {
			console.error('Failed to save watchlist:', err)
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
			console.log('WebSocket connected for trading platform')
			// Subscribe to all watchlist stocks
			watchlist.forEach(stock => {
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

					// Persist last-known values so they are available when market is closed
					try {
						localStorage.setItem(`ltp:${data.symbol}` , JSON.stringify({
							ltp: data.ltp,
							change_pct: data.change_pct,
							bid: data.bid,
							ask: data.ask,
							timestamp: data.timestamp,
							status: 'live'
						}))
					} catch (_) {}
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

	const addToWatchlist = (stock) => {
		if (!watchlist.find(s => s.symbol === stock.symbol)) {
			const newStock = {
				...stock,
				id: `${stock.symbol}_${Date.now()}`,
				addedAt: new Date().toISOString()
			}
			const newWatchlist = [...watchlist, newStock]
			setWatchlist(newWatchlist)
			saveWatchlist(newWatchlist)
			setSearchQuery('')
			setSearchResults([])
		}
	}

	const removeFromWatchlist = (stockId) => {
		const newWatchlist = watchlist.filter(s => s.id !== stockId)
		setWatchlist(newWatchlist)
		saveWatchlist(newWatchlist)
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

	const StockCard = ({ stock, showRemove = false, onRemove }) => {
		const liveData = livePrices[stock.symbol] || {}
		
		return (
			<div 
				className="stock-card"
				style={{
					border: '1px solid rgba(255,255,255,0.08)',
					borderRadius: '12px',
					padding: '16px',
					backgroundColor: 'var(--panel)',
					boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
					transition: 'all 0.3s ease',
					cursor: 'pointer'
				}}
				onMouseEnter={(e) => {
					e.currentTarget.style.transform = 'translateY(-2px)'
					e.currentTarget.style.boxShadow = '0 8px 24px rgba(0,0,0,0.25)'
				}}
				onMouseLeave={(e) => {
					e.currentTarget.style.transform = 'translateY(0)'
					e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)'
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
					{showRemove && (
						<button 
							className="remove-button"
							onClick={(e) => {
								e.stopPropagation()
								onRemove(stock.id)
							}}
							title="Remove from watchlist"
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
					)}
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
						{(() => {
							const cached = livePrices[stock.symbol]
							if (cached && (typeof cached.ltp === 'number' || typeof cached.change_pct === 'number')) {
								return (
									<div>
										<div style={{ marginBottom: '6px' }}>Showing last known values</div>
										<div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
											<span style={{ fontWeight: 'bold', color: 'var(--muted)' }}>LTP:</span>
											<span style={{ fontWeight: 'bold', color: 'var(--text)' }}>₹{formatPrice(cached.ltp)}</span>
										</div>
										<div style={{ display: 'flex', justifyContent: 'space-between' }}>
											<span style={{ fontWeight: 'bold', color: 'var(--muted)' }}>Change:</span>
											<span style={{ fontWeight: 'bold', color: getChangeColor(cached.change_pct) }}>{formatChange(cached.change_pct)}</span>
										</div>
										{(typeof cached.bid === 'number' || typeof cached.ask === 'number') && (
											<div style={{ marginTop: '8px', paddingTop: '8px', borderTop: '1px solid rgba(255,255,255,0.08)' }}>
												<div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: 'var(--muted)' }}>
													<span>Bid: ₹{formatPrice(cached.bid)}</span>
													<span>Ask: ₹{formatPrice(cached.ask)}</span>
												</div>
											</div>
										)}
										{cached.timestamp && (
											<div style={{ marginTop: '6px', fontSize: '11px', color: 'var(--muted)' }}>
												As of {new Date(cached.timestamp).toLocaleString()}
											</div>
										)}
									</div>
								)
							}
							return (
								<>
									<p style={{ margin: '0 0 4px 0' }}>Market is closed</p>
									<p style={{ margin: '0' }}>Live prices unavailable</p>
								</>
							)
						})()}
					</div>
				)}
			</div>
		)
	}

	return (
		<div className="enhanced-trading-platform">
			{/* Header */}
			<div className="trading-header" style={{ marginBottom: '24px' }}>
				<h1 style={{ color: 'var(--text)', marginBottom: '8px' }}>
					📈 Live Trading Platform
				</h1>
				<p style={{ color: 'var(--muted)', marginBottom: '20px' }}>
					Search stocks, add to watchlist, and monitor live prices
				</p>
				
				{/* Market Status */}
				<div className="market-status" style={{ marginBottom: '20px' }}>
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

				{/* Tabs */}
				<div className="tabs" style={{ display: 'flex', gap: '8px', marginBottom: '20px' }}>
					{['search', 'watchlist', 'trending'].map(tab => (
						<button
							key={tab}
							onClick={() => setSelectedTab(tab)}
							style={{
								padding: '8px 16px',
								border: '1px solid rgba(255,255,255,0.08)',
								borderRadius: '8px',
								backgroundColor: selectedTab === tab ? 'var(--accent)' : 'transparent',
								color: selectedTab === tab ? 'white' : 'var(--text)',
								cursor: 'pointer',
								textTransform: 'capitalize'
							}}
						>
							{tab === 'search' && '🔍 Search'}
							{tab === 'watchlist' && `📋 Watchlist (${watchlist.length})`}
							{tab === 'trending' && '📊 Trending'}
						</button>
					))}
				</div>
			</div>

			{/* Search Tab */}
			{selectedTab === 'search' && (
				<div className="search-section">
					{/* Search Input */}
					<div className="search-input-container" style={{ position: 'relative', marginBottom: '20px' }}>
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
								maxHeight: '400px',
								overflowY: 'auto',
								marginBottom: '20px'
							}}
						>
							<h3 style={{ color: 'var(--text)', margin: '15px', fontSize: '16px' }}>
								Search Results ({searchResults.length})
							</h3>
							<div className="results-grid" style={{
								display: 'grid',
								gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
								gap: '16px',
								padding: '15px'
							}}>
								{searchResults.map((stock) => (
									<div key={`${stock.symbol}_${stock.exchange}`}>
										<StockCard 
											stock={stock} 
											showRemove={false}
											onRemove={() => {}}
										/>
										<button
											onClick={() => addToWatchlist(stock)}
											style={{
												width: '100%',
												marginTop: '8px',
												padding: '8px',
												backgroundColor: 'var(--accent)',
												color: 'white',
												border: 'none',
												borderRadius: '6px',
												cursor: 'pointer',
												fontWeight: 'bold'
											}}
										>
											+ Add to Watchlist
										</button>
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
			)}

			{/* Watchlist Tab */}
			{selectedTab === 'watchlist' && (
				<div className="watchlist-section">
					{watchlist.length === 0 ? (
						<div 
							className="empty-watchlist"
							style={{
								textAlign: 'center',
								padding: '40px',
								color: 'var(--muted)',
								backgroundColor: 'rgba(255,255,255,0.03)',
								borderRadius: '10px',
								border: '2px dashed rgba(255,255,255,0.1)'
							}}
						>
							<h3>Your watchlist is empty</h3>
							<p>Search for stocks and add them to your watchlist to monitor live prices</p>
						</div>
					) : (
						<div 
							className="watchlist-grid"
							style={{
								display: 'grid',
								gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
								gap: '20px'
							}}
						>
							{watchlist.map((stock) => (
								<StockCard 
									key={stock.id}
									stock={stock} 
									showRemove={true}
									onRemove={removeFromWatchlist}
								/>
							))}
						</div>
					)}
				</div>
			)}

			{/* Trending Tab */}
			{selectedTab === 'trending' && (
				<div className="trending-section">
					<div 
						className="trending-placeholder"
						style={{
							textAlign: 'center',
							padding: '40px',
							color: 'var(--muted)',
							backgroundColor: 'rgba(255,255,255,0.03)',
							borderRadius: '10px',
							border: '2px dashed rgba(255,255,255,0.1)'
						}}
					>
						<h3>📊 Trending Stocks</h3>
						<p>This feature will show trending stocks based on volume and price movement</p>
						<p style={{ fontSize: '14px', marginTop: '10px' }}>
							Coming soon...
						</p>
					</div>
				</div>
			)}
		</div>
	)
}
