import React, { useState, useEffect, useRef } from 'react'

export default function OptionChainGrid({ isVisible, onClose }) {
	const [optionData, setOptionData] = useState({ calls: [], puts: [], underlying: null })
	const [expiryDates, setExpiryDates] = useState([])
	const [selectedExpiry, setSelectedExpiry] = useState('')
	const [loading, setLoading] = useState(false)
	const [error, setError] = useState('')
	const [underlyingPrice, setUnderlyingPrice] = useState(null)
	const [selectedStrike, setSelectedStrike] = useState(null)
	const [lastUpdate, setLastUpdate] = useState(null)
	const [autoRefresh, setAutoRefresh] = useState(true)
	const wsRef = useRef(null)
	const aliasToSideStrike = useRef(new Map())
	const tokenSubscribed = useRef(false)

	const apiBase = import.meta.env.VITE_API_BASE_URL || ''

	// Load expiry dates on component mount
	useEffect(() => {
		if (isVisible) {
			loadExpiryDates()
			loadUnderlyingPrice()
		}
	}, [isVisible])

	// Load option chain when expiry date changes
	useEffect(() => {
		if (selectedExpiry) {
			loadOptionChain()
		}
	}, [selectedExpiry])

	// Auto-refresh every 5 seconds (REST fallback for structure/volume/OI), WS drives LTP
	useEffect(() => {
		if (!isVisible || !autoRefresh) return

		const interval = setInterval(() => {
			if (selectedExpiry) {
				loadOptionChain()
			}
			loadUnderlyingPrice()
		}, 5000) // Refresh every 5 seconds

		return () => clearInterval(interval)
	}, [isVisible, autoRefresh, selectedExpiry])

	// WS connect/disconnect lifecycle
	useEffect(() => {
		if (!isVisible) {
			if (wsRef.current) {
				try { wsRef.current.close() } catch {}
				wsRef.current = null
			}
			return
		}
		const wsUrl = (apiBase || '').replace(/^http/, 'ws') + '/ws/ticks'
		const ws = new WebSocket(wsUrl)
		wsRef.current = ws
		ws.onopen = () => {
			// Subscribe after grid is loaded to get tokens/aliases
			trySubscribeOptionChain()
		}
		ws.onmessage = (ev) => {
			try {
				const msg = JSON.parse(ev.data)
				if (msg?.type === 'tick') {
					// Prefer alias mapping, else derive using option fields
					const sym = String(msg.symbol || '')
					const alias = sym.includes('|') ? sym : null
					let side, strike
					if (alias && aliasToSideStrike.current.has(alias)) {
						({ side, strike } = aliasToSideStrike.current.get(alias))
					} else if (msg?.strike_price && msg?.right_type) {
						strike = Number(msg.strike_price)
						const rt = String(msg.right_type).toUpperCase()
						side = rt === 'CE' || rt === 'CALL' ? 'call' : 'put'
					} else {
						return
					}
					const ltp = typeof msg.ltp === 'number' ? msg.ltp : Number(msg.ltp) || null
					if (ltp == null) return
					setOptionData((prev) => {
						const next = { ...prev }
						const list = side === 'call' ? [...next.calls] : [...next.puts]
						const idx = list.findIndex((r) => Number(r.strike_price) === Number(strike))
						if (idx >= 0) {
							list[idx] = { ...list[idx], ltp: ltp, last_price: ltp }
							if (side === 'call') next.calls = list; else next.puts = list
						}
						return next
					})
				}
			} catch {}
		}
		ws.onerror = () => {}
		ws.onclose = () => { wsRef.current = null; tokenSubscribed.current = false }
		return () => { try { ws.close() } catch {} }
	}, [isVisible])

	const loadExpiryDates = async () => {
		try {
			const response = await fetch(`${apiBase}/api/option-chain/expiry-dates`)
			const data = await response.json()
			
			if (data.success) {
				setExpiryDates(data.dates || [])
				// Set first expiry as default
				if (data.dates && data.dates.length > 0) {
					setSelectedExpiry(data.dates[0].iso_date)
				}
			}
		} catch (err) {
			console.error('Failed to load expiry dates:', err)
		}
	}

	const loadUnderlyingPrice = async () => {
		try {
			const response = await fetch(`${apiBase}/api/option-chain/underlying-price`)
			const data = await response.json()
			
			if (data.success) {
				setUnderlyingPrice(data.price)
			}
		} catch (err) {
			console.error('Failed to load underlying price:', err)
		}
	}

	const loadOptionChain = async () => {
		if (!selectedExpiry) return

		setLoading(true)
		setError('')
		
		try {
			const response = await fetch(
				`${apiBase}/api/option-chain/nifty50?expiry_date=${encodeURIComponent(selectedExpiry)}`
			)
			const data = await response.json()
			
			if (data.success) {
				setOptionData({
					calls: data.calls || [],
					puts: data.puts || [],
					underlying: data.underlying
				})
				setLastUpdate(new Date())
				
				// Update underlying price if available
				if (data.underlying_price) {
					setUnderlyingPrice(data.underlying_price)
				}
				// Build alias map for WS mapping: UNDER|EXPIRY|RIGHT|STRIKE
				aliasToSideStrike.current.clear()
				;(data.calls || []).forEach((c) => {
					const alias = `${'NIFTY'}|${selectedExpiry}|CALL|${c.strike_price}`
					aliasToSideStrike.current.set(alias, { side: 'call', strike: c.strike_price })
				})
				;(data.puts || []).forEach((p) => {
					const alias = `${'NIFTY'}|${selectedExpiry}|PUT|${p.strike_price}`
					aliasToSideStrike.current.set(alias, { side: 'put', strike: p.strike_price })
				})
				// Kick subscriptions
				trySubscribeOptionChain()
			} else {
				setError(data.error || 'Failed to load option chain')
			}
		} catch (err) {
			setError('Failed to load option chain data')
		} finally {
			setLoading(false)
		}
	}

	function trySubscribeOptionChain() {
		if (!wsRef.current || wsRef.current.readyState !== 1) return
		if (tokenSubscribed.current) return
		// Hit backend to subscribe all strikes with alias mapping
		fetch(`${apiBase}/api/option-chain/subscribe?stock_code=NIFTY&exchange_code=NFO&product_type=options&right=both&expiry_date=${encodeURIComponent(selectedExpiry)}&limit=200`, {
			method: 'POST'
		}).then(() => {
			tokenSubscribed.current = true
		}).catch(() => {})
	}

	const formatPrice = (price) => {
		if (typeof price !== 'number') return '--'
		return price.toFixed(2)
	}

	const formatVolume = (volume) => {
		if (typeof volume !== 'number') return '--'
		return volume.toLocaleString()
	}

	const getChangeColor = (change) => {
		if (typeof change !== 'number') return 'var(--muted)'
		return change >= 0 ? '#57d38c' : '#ff5c5c'
	}

	const getStrikeColor = (strike, underlying) => {
		if (!underlying || typeof strike !== 'number') return 'var(--text)'
		const diff = Math.abs(strike - underlying)
		const percentDiff = (diff / underlying) * 100
		
		if (percentDiff <= 2) return '#fbbf24' // Yellow for ATM
		if (percentDiff <= 5) return '#f59e0b' // Orange for near ATM
		return 'var(--text)' // Default for OTM/ITM
	}

	const handleStrikeClick = (strike) => {
		setSelectedStrike(selectedStrike === strike ? null : strike)
	}

	if (!isVisible) return null

	return (
		<div style={{
			position: 'fixed',
			top: 0,
			left: 0,
			right: 0,
			bottom: 0,
			backgroundColor: 'rgba(0, 0, 0, 0.8)',
			zIndex: 10000,
			display: 'flex',
			alignItems: 'center',
			justifyContent: 'center',
			padding: '20px'
		}}>
			<div style={{
				backgroundColor: '#0f141d',
				border: '1px solid rgba(255,255,255,0.1)',
				borderRadius: '12px',
				width: '100%',
				maxWidth: '1400px',
				maxHeight: '90vh',
				overflow: 'hidden',
				display: 'flex',
				flexDirection: 'column'
			}}>
				{/* Header */}
				<div style={{
					padding: '20px',
					borderBottom: '1px solid rgba(255,255,255,0.1)',
					display: 'flex',
					justifyContent: 'space-between',
					alignItems: 'center'
				}}>
					<div>
						<h2 style={{ color: 'var(--text)', margin: '0 0 8px 0' }}>
							NIFTY 50 Option Chain
						</h2>
						{underlyingPrice && (
							<div style={{ color: 'var(--muted)', fontSize: '14px' }}>
								Underlying: ₹{formatPrice(underlyingPrice)}
								{lastUpdate && (
									<span style={{ 
										color: 'var(--muted)',
										marginLeft: '8px',
										fontSize: '12px'
									}}>
										Last updated: {lastUpdate.toLocaleTimeString()}
									</span>
								)}
							</div>
						)}
					</div>
					<div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
						<button
							onClick={() => {
								if (selectedExpiry) {
									loadOptionChain()
								}
								loadUnderlyingPrice()
							}}
							disabled={loading}
							style={{
								background: 'var(--primary)',
								color: 'white',
								border: 'none',
								borderRadius: '6px',
								padding: '6px 12px',
								cursor: loading ? 'not-allowed' : 'pointer',
								fontSize: '12px',
								fontWeight: '600',
								opacity: loading ? 0.6 : 1
							}}
						>
							{loading ? 'Loading...' : 'Refresh'}
						</button>
						<label style={{ 
							display: 'flex', 
							alignItems: 'center', 
							gap: '4px', 
							fontSize: '12px', 
							color: 'var(--muted)',
							cursor: 'pointer'
						}}>
							<input
								type="checkbox"
								checked={autoRefresh}
								onChange={(e) => setAutoRefresh(e.target.checked)}
								style={{ margin: 0 }}
							/>
							Auto-refresh
						</label>
						<button
							onClick={onClose}
							style={{
								background: 'var(--danger)',
								color: 'white',
								border: 'none',
								borderRadius: '6px',
								padding: '8px 16px',
								cursor: 'pointer',
								fontSize: '14px'
							}}
						>
							Close
						</button>
					</div>
				</div>

				{/* Controls */}
				<div style={{
					padding: '16px 20px',
					borderBottom: '1px solid rgba(255,255,255,0.1)',
					display: 'flex',
					gap: '16px',
					alignItems: 'center'
				}}>
					<div>
						<label style={{ color: 'var(--muted)', fontSize: '14px', marginRight: '8px' }}>
							Expiry Date:
						</label>
						<select
							value={selectedExpiry}
							onChange={(e) => setSelectedExpiry(e.target.value)}
							style={{
								background: '#1a1f2e',
								color: 'var(--text)',
								border: '1px solid rgba(255,255,255,0.1)',
								borderRadius: '6px',
								padding: '6px 12px',
								fontSize: '14px'
							}}
						>
							{expiryDates.map((date) => (
								<option key={date.iso_date} value={date.iso_date}>
									{date.display}
								</option>
							))}
						</select>
					</div>
					
					{loading && (
						<div style={{ color: 'var(--accent)', fontSize: '14px' }}>
							Loading option chain...
						</div>
					)}
				</div>

				{/* Error Message */}
				{error && (
					<div style={{
						padding: '16px 20px',
						backgroundColor: 'rgba(255, 92, 92, 0.1)',
						borderLeft: '4px solid var(--danger)',
						color: 'var(--danger)',
						fontSize: '14px'
					}}>
						{error}
					</div>
				)}

				{/* Option Chain Grid */}
				<div style={{
					flex: 1,
					overflow: 'auto',
					padding: '20px'
				}}>
					<div style={{
						display: 'grid',
						gridTemplateColumns: '1fr 80px 1fr',
						gap: '0',
						fontSize: '12px',
						minWidth: '800px'
					}}>
						{/* Calls Header */}
						<div style={{
							textAlign: 'center',
							fontWeight: 'bold',
							color: '#57d38c',
							padding: '8px',
							backgroundColor: 'rgba(87, 211, 140, 0.1)',
							borderRadius: '6px 0 0 6px'
						}}>
							CALLS
						</div>
						
						{/* Strike Price Header */}
						<div style={{
							textAlign: 'center',
							fontWeight: 'bold',
							color: 'var(--text)',
							padding: '8px',
							backgroundColor: 'rgba(255,255,255,0.05)',
							display: 'flex',
							alignItems: 'center',
							justifyContent: 'center'
						}}>
							STRIKE
						</div>
						
						{/* Puts Header */}
						<div style={{
							textAlign: 'center',
							fontWeight: 'bold',
							color: '#ff5c5c',
							padding: '8px',
							backgroundColor: 'rgba(255, 92, 92, 0.1)',
							borderRadius: '0 6px 6px 0'
						}}>
							PUTS
						</div>

						{/* Option Chain Data */}
						{optionData.calls.length > 0 && optionData.puts.length > 0 ? (
							<>
								{/* Calls Column */}
								<div>
									{optionData.calls.map((call, index) => (
										<div
											key={index}
											style={{
												display: 'grid',
												gridTemplateColumns: '1fr 1fr 1fr 1fr',
												gap: '1px',
												backgroundColor: 'rgba(255,255,255,0.02)',
												borderRadius: index === 0 ? '6px 0 0 0' : '0',
												padding: '4px 0'
											}}
										>
											<div style={{ textAlign: 'center', color: 'var(--text)' }}>
												{formatPrice(call.last_price || call.ltp)}
											</div>
											<div style={{ textAlign: 'center', color: 'var(--muted)' }}>
												{formatVolume(call.volume)}
											</div>
											<div style={{ textAlign: 'center', color: 'var(--muted)' }}>
												{formatVolume(call.open_interest || call.oi)}
											</div>
											<div style={{ 
												textAlign: 'center', 
												color: getChangeColor(call.change || call.change_percent)
											}}>
												{formatPrice(call.change || call.change_percent)}
											</div>
										</div>
									))}
								</div>

								{/* Strike Price Column */}
								<div>
									{optionData.calls.map((call, index) => (
										<div
											key={index}
											onClick={() => handleStrikeClick(call.strike_price)}
											style={{
												textAlign: 'center',
												fontWeight: 'bold',
												color: getStrikeColor(call.strike_price, underlyingPrice?.last_price || underlyingPrice?.close),
												padding: '8px 4px',
												backgroundColor: selectedStrike === call.strike_price 
													? 'rgba(79, 156, 255, 0.2)' 
													: 'rgba(255,255,255,0.05)',
												cursor: 'pointer',
												borderRadius: selectedStrike === call.strike_price ? '4px' : '0'
											}}
										>
											{formatPrice(call.strike_price)}
										</div>
									))}
								</div>

								{/* Puts Column */}
								<div>
									{optionData.puts.map((put, index) => (
										<div
											key={index}
											style={{
												display: 'grid',
												gridTemplateColumns: '1fr 1fr 1fr 1fr',
												gap: '1px',
												backgroundColor: 'rgba(255,255,255,0.02)',
												borderRadius: index === 0 ? '0 6px 0 0' : '0',
												padding: '4px 0'
											}}
										>
											<div style={{ textAlign: 'center', color: 'var(--text)' }}>
												{formatPrice(put.last_price || put.ltp)}
											</div>
											<div style={{ textAlign: 'center', color: 'var(--muted)' }}>
												{formatVolume(put.volume)}
											</div>
											<div style={{ textAlign: 'center', color: 'var(--muted)' }}>
												{formatVolume(put.open_interest || put.oi)}
											</div>
											<div style={{ 
												textAlign: 'center', 
												color: getChangeColor(put.change || put.change_percent)
											}}>
												{formatPrice(put.change || put.change_percent)}
											</div>
										</div>
									))}
								</div>
							</>
						) : (
							<div style={{
								gridColumn: '1 / -1',
								textAlign: 'center',
								color: 'var(--muted)',
								padding: '40px',
								fontSize: '16px'
							}}>
								{loading ? 'Loading option chain...' : 'No option chain data available'}
							</div>
						)}
					</div>

					{/* Column Headers for Data */}
					<div style={{
						display: 'grid',
						gridTemplateColumns: '1fr 80px 1fr',
						gap: '0',
						marginTop: '8px',
						fontSize: '10px',
						color: 'var(--muted)'
					}}>
						<div style={{ textAlign: 'center' }}>
							<div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: '1px' }}>
								<span>LTP</span>
								<span>VOL</span>
								<span>OI</span>
								<span>CHG</span>
							</div>
						</div>
						<div></div>
						<div style={{ textAlign: 'center' }}>
							<div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: '1px' }}>
								<span>LTP</span>
								<span>VOL</span>
								<span>OI</span>
								<span>CHG</span>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>
	)
}
