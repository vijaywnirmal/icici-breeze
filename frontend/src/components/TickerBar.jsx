import React, { useEffect, useMemo, useRef, useState } from 'react'
import { useRouter } from 'next/router'
import GenericOptionChainGrid from './GenericOptionChainGrid'
import CustomerProfile from './CustomerProfile'
import Navigation from './Navigation'
import { INDEX_CONFIGS } from '../config/indexConfigs'
// Import moved to pages/_app.jsx to satisfy Next.js global CSS rule

const WS_PATH = '/ws/stocks'

export default function TickerBar() {
	const router = useRouter()
	
	// Define the NSE indexes with their Breeze tokens
	const nseIndexes = [
		{ token: '4.1!NIFTY 50', name: 'NIFTY' },
		{ token: '4.1!NIFTY BANK', name: 'BANKNIFTY' },
		{ token: '4.1!NIFTY FIN SERVICE', name: 'FINNIFTY' },
	]

	const [indexData, setIndexData] = useState({})
	const [wsConnected, setWsConnected] = useState(false)
	const [showOptionChain, setShowOptionChain] = useState(false)
	const [selectedIndexConfig, setSelectedIndexConfig] = useState(null)
	const [tickerPaused, setTickerPaused] = useState(false)
	const [showSettings, setShowSettings] = useState(false)
	const settingsRef = useRef(null)
	const [visibleIndices, setVisibleIndices] = useState({
		'NIFTY': true,
		'BANKNIFTY': true,
		'FINNIFTY': true
	})
	const [tickerSpeed, setTickerSpeed] = useState(60)

	const apiBase = (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_BASE_URL) || ''
	const wsBase = (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_BASE_WS) || ''
	const httpBase = useMemo(() => (apiBase || 'http://127.0.0.1:8000').replace(/\/$/, ''), [apiBase])
	const wsUrl = useMemo(() => {
		const base = (wsBase || httpBase || '').replace(/\/$/, '')
		if (base.startsWith('ws://') || base.startsWith('wss://')) return `${base}${WS_PATH}`
		if (base.startsWith('http://')) return `ws://${base.substring('http://'.length)}${WS_PATH}`
		if (base.startsWith('https://')) return `wss://${base.substring('https://'.length)}${WS_PATH}`
		return `ws://127.0.0.1:8000${WS_PATH}`
	}, [httpBase, wsBase])

	const wsRef = useRef(null)
	const subscribedSymbolsRef = useRef([])
	const retryRef = useRef(0)
	const pollTimer = useRef(null)
	const liveTimer = useRef(null)
	const didInitialPollRef = useRef(false)

	const formatNumber = (num) => {
		if (typeof num !== 'number') return '--'
		try { return num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) } catch { return String(num) }
	}

	const getIndexData = (token) => {
		return indexData[token] || { 
			last: null, 
			change: null, 
			close: null,
			stock_name: null,
			timestamp: null,
			status: 'closed'
		}
	}

	const getDerivedData = (token) => {
		const data = getIndexData(token)
		const change = typeof data.change === 'number' ? data.change : null
		const close = typeof data.close === 'number' ? data.close : null
		const last = typeof data.last === 'number' ? data.last : null
		
		// Calculate percentage change
		let percentChange = null
		if (change !== null && close !== null && close !== 0) {
			percentChange = (change / close) * 100
		}
		
		return { change, close, last, percentChange }
	}

	const handleIndexClick = (indexName) => {
		const config = INDEX_CONFIGS[indexName]
		if (config) {
			setSelectedIndexConfig(config)
			setShowOptionChain(true)
		}
	}

	const handleCloseOptionChain = () => {
		setShowOptionChain(false)
		setSelectedIndexConfig(null)
	}

	const handleToggleIndex = (indexName) => {
		setVisibleIndices(prev => ({
			...prev,
			[indexName]: !prev[indexName]
		}))
	}

	const handleResetSettings = () => {
		setVisibleIndices({
			'NIFTY': true,
			'BANKNIFTY': true,
			'FINNIFTY': true
		})
		setTickerSpeed(60)
	}

	// Handle click outside to close settings dropdown
	useEffect(() => {
		function handleClickOutside(event) {
			if (settingsRef.current && !settingsRef.current.contains(event.target)) {
				setShowSettings(false)
			}
		}

		if (showSettings) {
			document.addEventListener('mousedown', handleClickOutside)
			return () => document.removeEventListener('mousedown', handleClickOutside)
		}
	}, [showSettings])

	const handleSpeedChange = (e) => {
		setTickerSpeed(parseInt(e.target.value))
	}


		useEffect(() => {
		let closed = false

		// Seed from localStorage so prices persist across refresh
		try {
			const savedData = {}
			nseIndexes.forEach(index => {
				const saved = JSON.parse(localStorage.getItem(`ticker:${index.token}`) || 'null')
				if (saved && typeof saved === 'object') {
					savedData[index.token] = saved
				}
			})
			if (Object.keys(savedData).length > 0) {
				setIndexData(savedData)
			}
		} catch (_) {}

		function scheduleReconnect() {
			const retry = Math.min(30000, 1000 * Math.pow(2, retryRef.current || 0))
			retryRef.current = (retryRef.current || 0) + 1
			clearTimeout(liveTimer.current)
			liveTimer.current = setTimeout(connect, retry)
		}

		async function pollSnapshot() {
			if (didInitialPollRef.current) return
			try {
				// Get API session from sessionStorage
				const apiSession = sessionStorage.getItem('api_session')
				const indexUrl = apiSession 
					? `${httpBase}/api/nse/indexes?api_session=${apiSession}`
					: `${httpBase}/api/nse/indexes`
				
				// Fetch index data from get_quotes API (for market closed hours)
				const indexRes = await fetch(indexUrl)
				const indexJson = await indexRes.json().catch(() => ({}))
				
				
				if (!closed) {
					didInitialPollRef.current = true
					
					// Update index data from get_quotes
					if (indexJson && indexJson.success && indexJson.message && Array.isArray(indexJson.message.indexes)) {
						const newIndexData = {}
						indexJson.message.indexes.forEach(index => {
							newIndexData[index.token] = {
								last: index.last,
								change: index.change,
								close: index.close,
								stock_name: index.stock_name,
								timestamp: index.timestamp,
								status: index.status || 'closed'
							}
						})
						setIndexData(prev => ({ ...prev, ...newIndexData }))
					} else if (indexJson && !indexJson.success) {
						console.log('Index data fetch failed:', indexJson.message)
						// Don't set placeholder data - let the UI handle empty state gracefully
					}
					
				}
			} catch (_) {
				// ignore polling errors
			}
		}

		function startPollingOnce() {
			clearInterval(pollTimer.current)
			pollTimer.current = null
			pollSnapshot()
		}

		function stopPolling() {
			clearInterval(pollTimer.current)
		}

		async function connect() {
			if (closed) return
			stopPolling()

			// Check if market is open - if not, use polling instead of WebSocket
			try {
				const marketStatusRes = await fetch(`${httpBase}/api/market/status`)
				const marketStatus = await marketStatusRes.json().catch(() => ({ is_open: false }))
				
				if (!marketStatus.is_open) {
					// Market is closed, use polling instead of WebSocket
					setWsConnected(false)
					startPollingOnce()
					return
				}
			} catch (_) {
				// If we can't check market status, proceed with WebSocket
			}

			const ws = new WebSocket(wsUrl)
			wsRef.current = ws

			ws.onopen = async () => {
				retryRef.current = 0
				setWsConnected(true)
				try {
					// Subscribe to all NSE indexes
					const indexSymbols = nseIndexes.map(index => ({
						stock_code: index.token,
						token: index.token,
						exchange_code: 'NSE',
						product_type: 'cash'
					}))
					
					// Subscribe to Nifty 50 stocks
					const apiSession = sessionStorage.getItem('api_session')
					const url = apiSession 
						? `${httpBase}/api/nifty50/stocks?api_session=${apiSession}`
						: `${httpBase}/api/nifty50/stocks`
					const res = await fetch(url)
					const json = await res.json().catch(() => null)
					const items = Array.isArray(json?.stocks) ? json.stocks : []
					
					const subs = items.map(it => ({ 
						stock_code: (it.stock_code || it.symbol || '').toUpperCase(), 
						token: it.token || undefined, 
						exchange_code: 'NSE', 
						product_type: 'cash' 
					}))
					
					const symbols = [...indexSymbols, ...subs].filter(s => s.stock_code)
					subscribedSymbolsRef.current = symbols
					ws.send(JSON.stringify({ action: 'subscribe_many', symbols }))
				} catch (_) {}
			}

			ws.onmessage = (evt) => {
				try {
					const payload = JSON.parse(evt.data)
					if (payload && payload.type === 'tick' && payload.symbol) {
						const sym = String(payload.symbol).toUpperCase()
						
						
						// Check if this is one of our NSE indexes
						const matchingIndex = nseIndexes.find(index => 
							sym === index.token || sym.includes(index.token.replace('4.1!', ''))
						)
						
						if (matchingIndex) {
							// Calculate change from ltp and close
							const ltp = payload.ltp
							const close = payload.close
							const change = ltp && close ? ltp - close : null
							
							
							setIndexData(prev => ({
								...prev,
								[matchingIndex.token]: {
									...prev[matchingIndex.token],
									last: ltp ?? prev[matchingIndex.token]?.last,
									change: change ?? prev[matchingIndex.token]?.change,
									close: close ?? prev[matchingIndex.token]?.close,
									stock_name: payload.stock_name ?? prev[matchingIndex.token]?.stock_name,
									timestamp: payload.timestamp ?? prev[matchingIndex.token]?.timestamp,
									status: 'live'
								}
							}))
							
							// Persist to localStorage
							try { 
								localStorage.setItem(`ticker:${matchingIndex.token}`, JSON.stringify({ 
									last: ltp ?? undefined, 
									change: change ?? undefined, 
									close: close ?? undefined,
									stock_name: payload.stock_name ?? undefined, 
									timestamp: payload.timestamp ?? undefined, 
									status: 'live' 
								})) 
							} catch (_) {}
						}
						
					}
				} catch (_) { /* ignore */ }
			}

			ws.onerror = () => {
				setWsConnected(false)
				startPollingOnce()
			}
			
			ws.onclose = () => {
				setWsConnected(false)
				startPollingOnce()
				scheduleReconnect()
			}
		}

		// Always fetch once on mount so a price appears even before WS
		connect()

		return () => {
			closed = true
			try {
				if (wsRef.current?.readyState === WebSocket.OPEN) {
					// Unsubscribe from all symbols
					const symbols = subscribedSymbolsRef.current || []
					if (symbols.length) {
						wsRef.current.send(JSON.stringify({ action: 'unsubscribe_many', symbols }))
					}
				}
				wsRef.current?.close()
			} catch (_) {}
			stopPolling()
			clearTimeout(liveTimer.current)
		}
	}, [httpBase, wsUrl])

		return (
		<>
			{/* Main Header with Title, Nav and Profile */}
			<div className="main-header">
				{/* Left side - Icon and Title */}
				<div className="header-left">
					<button
						className="logo-button-minimal"
						onClick={() => router.push('/')}
					>
						<svg width="18" height="18" viewBox="0 0 24 24" fill="none">
							<path d="M12 2L2 7l10 5 10-5-10-5z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
							<path d="M2 17l10 5 10-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
							<path d="M2 12l10 5 10-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
						</svg>
					</button>
					<div className="header-title">
						<h1 className="main-title">Breeze Trading Platform</h1>
						<p className="main-subtitle">Your comprehensive trading and strategy development platform</p>
					</div>
				</div>

				{/* Right side - App Navigation + Profile */}
				<div className="header-right">
					<nav className="header-nav">
						<button className="nav-chip" onClick={() => router.push('/live-trading')}>Live Trading</button>
						<button className="nav-chip" onClick={() => router.push('/backtest')}>Backtest Strategy</button>
						<button className="nav-chip" onClick={() => router.push('/builder')}>Strategy Builder</button>
						<button className="nav-chip" onClick={() => router.push('/results')}>View Results</button>
					</nav>
					<CustomerProfile />
				</div>
			</div>

			{/* Professional Ticker Bar */}
			<div className="ticker-bar-container">
				{/* Left Pause Control */}
				<div className="ticker-controls-left">
					<button 
						className="ticker-pause-btn"
						onClick={() => setTickerPaused(!tickerPaused)}
					>
						{tickerPaused ? (
							<svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="0 0 24 24" height="16" width="16">
								<path fill="currentColor" d="M8 5v14l11-7z"/>
							</svg>
						) : (
							<svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="0 0 24 24" height="16" width="16">
								<path fill="currentColor" d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
							</svg>
						)}
					</button>
				</div>

				{/* Marquee Ticker */}
				<div className="ticker-marquee-container">
					<div 
						className={`ticker-marquee ${tickerPaused ? 'paused' : ''}`}
						style={{ '--animation-duration': `${tickerSpeed}s` }}
					>
						{nseIndexes.filter(index => visibleIndices[index.name]).map((index, i) => {
							const data = getIndexData(index.token)
							const derived = getDerivedData(index.token)
							const displayPrice = data.last
							const change = derived.change
							const percentChange = derived.percentChange
							const displayName = index.name
							
							return (
								<div key={index.token} className="ticker-item-marquee">
									<div className="ticker-item-content" onClick={INDEX_CONFIGS[index.name] ? () => handleIndexClick(index.name) : undefined}>
										<span className="ticker-symbol">{displayName}</span>
										<div className="ticker-data">
											<span className="ticker-price">{displayPrice ? formatNumber(displayPrice) : '--'}</span>
											<span className={`ticker-change ${change > 0 ? 'positive' : change < 0 ? 'negative' : 'neutral'}`}>
												{change !== null ? (
													<>
														{change > 0 ? '+' : ''}{formatNumber(Math.abs(change))}
														<span className="ticker-percent">
															({percentChange > 0 ? '+' : ''}{percentChange?.toFixed(2)}%)
														</span>
														<svg className="ticker-arrow" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 26 26" fill="none">
															<path fillRule="evenodd" clipRule="evenodd" d={change > 0 ? 
																"M18.593 15.8051C19.0376 15.4776 19.1326 14.8516 18.8051 14.4069C18.5507 14.0615 18.2963 13.7332 18.0731 13.4472C17.6276 12.8764 17.0143 12.1118 16.3479 11.3444C15.6859 10.5819 14.9518 9.79361 14.2666 9.18811C13.9251 8.88637 13.5721 8.60888 13.2279 8.4014C12.9112 8.21046 12.476 8 11.9999 8C11.5238 8 11.0885 8.21046 10.7718 8.4014C10.4276 8.60888 10.0747 8.88637 9.7332 9.18811C9.04791 9.79361 8.31387 10.5819 7.65183 11.3444C6.98548 12.1118 6.37216 12.8764 5.92664 13.4472C5.70347 13.7332 5.44902 14.0615 5.19463 14.4069C4.86712 14.8516 4.96211 15.4776 5.4068 15.8051C5.58556 15.9368 5.79362 16.0002 5.99982 16L11.9999 16L17.9999 16C18.2061 16.0002 18.4142 15.9368 18.593 15.8051Z" :
																"M18.593 8.19486C19.0376 8.52237 19.1326 9.14837 18.8051 9.59306C18.5507 9.93847 18.2963 10.2668 18.0731 10.5528C17.6276 11.1236 17.0143 11.8882 16.3479 12.6556C15.6859 13.4181 14.9518 14.2064 14.2666 14.8119C13.9251 15.1136 13.5721 15.3911 13.2279 15.5986C12.9112 15.7895 12.476 16 11.9999 16C11.5238 16 11.0885 15.7895 10.7718 15.5986C10.4276 15.3911 10.0747 15.1136 9.7332 14.8119C9.04791 14.2064 8.31387 13.4181 7.65183 12.6556C6.98548 11.8882 6.37216 11.1236 5.92664 10.5528C5.70347 10.2668 5.44902 9.93847 5.19463 9.59307C4.86712 9.14837 4.96211 8.52237 5.4068 8.19486C5.58556 8.0632 5.79362 7.99983 5.99982 8L11.9999 8L17.9999 8C18.2061 7.99983 18.4142 8.0632 18.593 8.19486Z"
															} fill="currentColor"/>
														</svg>
													</>
												) : (
													'No data'
												)}
											</span>
										</div>
									</div>
								</div>
							)
						})}
					</div>
				</div>

				{/* Right Control Buttons */}
				<div className="ticker-controls-right">
					<div className="settings-dropdown-container">
						<div style={{ position: 'relative' }}>
							<button 
								className="ticker-control-btn"
								onClick={() => setShowSettings(!showSettings)}
								title="Edit Columns"
							>
								<svg width="15" height="15" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
									<path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" stroke="currentColor" strokeWidth="2"/>
									<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1Z" stroke="currentColor" strokeWidth="2"/>
								</svg>
							</button>
							{showSettings && (
								<div
									ref={settingsRef}
									style={{
										position: 'absolute',
										top: '100%',
										right: '0',
										marginTop: '8px',
										background: '#1a1a1a',
										border: '1px solid #333',
										borderRadius: '8px',
										padding: '16px',
										minWidth: '280px',
										zIndex: 9999,
										boxShadow: '0 4px 12px rgba(0, 0, 0, 0.3)'
									}}
									onClick={(e) => e.stopPropagation()}
								>
									<div style={{ marginBottom: '12px', fontSize: '14px', fontWeight: '600', color: '#fff' }}>
										Edit Columns
									</div>
									<div style={{ marginBottom: '16px' }}>
										{Object.entries(visibleIndices).map(([index, visible]) => (
											<label
												key={index}
												style={{
													display: 'flex',
													alignItems: 'center',
													marginBottom: '8px',
													cursor: 'pointer',
													color: '#fff'
												}}
											>
												<input
													type="checkbox"
													checked={visible}
													onChange={(e) => setVisibleIndices(prev => ({
														...prev,
														[index]: e.target.checked
													}))}
													style={{ marginRight: '8px' }}
												/>
												{index}
											</label>
										))}
									</div>
									<button
										onClick={handleResetSettings}
										style={{
											background: '#333',
											color: '#fff',
											border: '1px solid #555',
											borderRadius: '4px',
											padding: '6px 12px',
											fontSize: '12px',
											cursor: 'pointer',
											marginBottom: '12px'
										}}
									>
										Reset to Default
									</button>
									<div style={{ marginBottom: '8px', fontSize: '12px', color: '#ccc' }}>
										Ticker Speed: {tickerSpeed}s
									</div>
									<input
										type="range"
										min="10"
										max="300"
										step="10"
										value={tickerSpeed}
										onChange={handleSpeedChange}
										style={{
											width: '100%',
											height: '4px',
											background: '#333',
											borderRadius: '2px',
											outline: 'none',
											cursor: 'pointer'
										}}
									/>
								</div>
							)}
						</div>
						
					</div>
				</div>
			</div>

			{/* Generic Option Chain Modal */}
			{selectedIndexConfig && (
				<GenericOptionChainGrid 
					isVisible={showOptionChain}
					onClose={handleCloseOptionChain}
					indexConfig={selectedIndexConfig}
					underlyingPrice={selectedIndexConfig ? (() => {
						const token = selectedIndexConfig.symbol === 'NIFTY' ? '4.1!NIFTY 50' : 
									selectedIndexConfig.symbol === 'BANKNIFTY' ? '4.1!NIFTY BANK' : '4.1!NIFTY FIN SERVICE'
						const data = getIndexData(token)
						return data.last || data.close
					})() : null}
				/>
			)}



		</>
	)
}
