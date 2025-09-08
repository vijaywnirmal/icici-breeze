import React, { useEffect, useMemo, useRef, useState } from 'react'
import GenericOptionChainGrid from './GenericOptionChainGrid'
import { INDEX_CONFIGS } from '../config/indexConfigs'

const WS_PATH = '/ws/stocks'

export default function TickerBar() {
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

	const apiBase = import.meta.env.VITE_API_BASE_URL || ''
	const wsBase = import.meta.env.VITE_API_BASE_WS || ''
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
						// Set placeholder data to show the ticker structure
						const placeholderData = {}
						nseIndexes.forEach(index => {
							placeholderData[index.token] = {
								last: null,
								change: null,
								close: null,
								stock_name: index.name,
								timestamp: null,
								status: 'no_data'
							}
						})
						setIndexData(placeholderData)
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
		<div style={{position: 'relative'}}>
			{/* Minimalistic Ticker Bar */}
			<div 
				className="ticker-scroll"
				style={{
					display: 'flex',
					alignItems: 'center',
					background: 'var(--panel)',
					border: '1px solid var(--border)',
					borderRadius: 'var(--radius)',
					padding: 'var(--space-4)',
					width: '100%',
					overflowX: 'auto',
					overflowY: 'hidden',
					gap: 'var(--space-6)'
				}}
			>
				{nseIndexes.map((index, i) => {
					const data = getIndexData(index.token)
					const derived = getDerivedData(index.token)
					const displayPrice = data.last
					const change = derived.change
					const percentChange = derived.percentChange
					const color = change > 0 ? 'var(--success)' : change < 0 ? 'var(--danger)' : 'var(--text-muted)'
					const displayName = index.name
					
					return (
						<React.Fragment key={index.token}>
							<div style={{
								display: 'flex',
								alignItems: 'center',
								gap: 'var(--space-3)',
								cursor: INDEX_CONFIGS[index.name] ? 'pointer' : 'default',
								minWidth: 'fit-content',
								whiteSpace: 'nowrap',
								padding: 'var(--space-2) var(--space-3)',
								borderRadius: 'var(--radius)',
								...(INDEX_CONFIGS[index.name] && {
									backgroundColor: 'var(--panel-hover)'
								})
							}} onClick={
								INDEX_CONFIGS[index.name] ? () => handleIndexClick(index.name) : undefined
							}>
								{/* Index Name */}
								<div style={{
									fontWeight: 600,
									fontSize: '14px',
									color: 'var(--text)',
									fontFamily: 'var(--font-sans)'
								}}>
									{displayName}
								</div>
								{/* Current Price (LTP) */}
								<div style={{
									fontSize: '14px',
									fontWeight: 500,
									color: 'var(--text)',
									fontFamily: 'var(--font-mono)'
								}}>
									₹{displayPrice ? formatNumber(displayPrice) : '--'}
								</div>
								{/* Change (absolute and %) - values only */}
								{change !== null ? (
									<div style={{
										display: 'flex',
										alignItems: 'center',
										gap: '6px'
									}}>
										<div style={{
											fontSize: '14px',
											fontWeight: 700,
											color: color
										}}>
											{formatNumber(Math.abs(change))}
										</div>
										{percentChange !== null && (
											<div style={{
												fontSize: '14px',
												fontWeight: 700,
												color: color
											}}>
												{percentChange.toFixed(2)}%
											</div>
										)}
									</div>
								) : data.status === 'no_data' ? (
									<div style={{
										fontSize: '12px',
										color: '#9ca3af'
									}}>
										Login required
									</div>
								) : (
									<div style={{
										fontSize: '12px',
										color: '#9ca3af'
									}}>
										No change data
									</div>
								)}
								{/* Loading indicator */}
								{/* WebSocket connection indicator */}
								{!wsConnected && (
									<div style={{
										fontSize: '10px',
										color: '#f59e0b',
										marginLeft: '4px'
									}}>
										●
									</div>
								)}
							</div>
							{/* Separator line */}
							{i < nseIndexes.length - 1 && (
								<div style={{
									width: '1px',
									height: '20px',
									background: 'rgba(255,255,255,0.08)',
									margin: '0 8px'
								}} />
							)}
						</React.Fragment>
					)
				})}
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
		</div>
	)
}
