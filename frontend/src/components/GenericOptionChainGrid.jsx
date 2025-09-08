import React, { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'

export default function GenericOptionChainGrid({ 
	isVisible, 
	onClose, 
	indexConfig,
	underlyingPrice: realUnderlyingPrice
}) {
	const [optionData, setOptionData] = useState({ calls: [], puts: [], underlying: null })
	const [expiryDates, setExpiryDates] = useState([])
	const [selectedExpiry, setSelectedExpiry] = useState('')
	const [loading, setLoading] = useState(false)
	const [error, setError] = useState('')
	const [underlyingPrice, setUnderlyingPrice] = useState(realUnderlyingPrice ? { last_price: realUnderlyingPrice, close: realUnderlyingPrice } : null)
	const [selectedStrike, setSelectedStrike] = useState(null)
	const [lastUpdate, setLastUpdate] = useState(null)
	const wsRef = useRef(null)
	const aliasToSideStrike = useRef(new Map())
	const tokenSubscribed = useRef(false)
	// Tiny visual throttle and flash indication
	const visualThrottleMs = 120
	const pendingMiniRef = useRef(new Map())
	const miniTimerRef = useRef(null)
	const lastLtpRef = useRef(new Map())
	const flashRef = useRef(new Map())
	const [flashTick, setFlashTick] = useState(0)
	const [userSelectedExpiry, setUserSelectedExpiry] = useState(false)
	const [didAutoSubscribe, setDidAutoSubscribe] = useState(false)

	const apiBase = import.meta.env.VITE_API_BASE_URL || ''

	// Update underlying price when real price changes
	useEffect(() => {
		if (realUnderlyingPrice) {
			setUnderlyingPrice({ last_price: realUnderlyingPrice, close: realUnderlyingPrice })
		}
	}, [realUnderlyingPrice])

	// Load expiry dates on component mount
	useEffect(() => {
		if (isVisible) {
			loadExpiryDates()
			if (!realUnderlyingPrice) {
				loadUnderlyingPrice()
			}
		}
	}, [isVisible])

	// Load option chain when component becomes visible or underlying price changes
	useEffect(() => {
		if (isVisible) {
			loadOptionChain()
		}
	}, [isVisible, selectedExpiry])

	// Trigger subscription when expiry changes
	useEffect(() => {
		if (isVisible && selectedExpiry) {
			// Unsubscribe previous option subscriptions (if any)
			try {
				if (wsRef.current && wsRef.current.readyState === 1) {
					wsRef.current.send(JSON.stringify({ action: 'unsubscribe_options' }))
				}
			} catch {}
			// Reset and clear current rows to avoid mixing expiries
			tokenSubscribed.current = false
			setDidAutoSubscribe(false)
			setOptionData((prev) => ({ ...prev, calls: [], puts: [], expiry_date: selectedExpiry }))
			// Subscription will occur after fresh data loads
		}
	}, [selectedExpiry])

	// WS connect/disconnect lifecycle
	useEffect(() => {
		if (!isVisible) {
			if (wsRef.current) {
				try { wsRef.current.close() } catch {}
				wsRef.current = null
			}
			return
		}
		const wsUrl = (apiBase || '').replace(/^http/, 'ws') + '/ws/options'
		const ws = new WebSocket(wsUrl)
		wsRef.current = ws
		ws.onopen = () => {
			// Subscribe immediately if we have context; else retry shortly
			try {
				if (selectedExpiry) {
					if ((optionData.calls || []).length > 0 || (optionData.puts || []).length > 0) {
						subscribeToOptions()
					} else {
						setTimeout(() => {
							if (wsRef.current && wsRef.current.readyState === 1) {
								subscribeToOptions()
							}
						}, 600)
					}
				}
			} catch {}
		}
		ws.onmessage = (ev) => {
			try {
				const msg = JSON.parse(ev.data)
				console.log('🔍 Options WebSocket message received:', msg)
				
				// Handle subscription confirmation messages
				if (msg.type === 'subscribed' && msg.underlying) {
					console.log('✅ Options subscription confirmed:', msg)
					return
				}
				
				// Handle error messages
				if (msg.type === 'error') {
					console.error('❌ Options WebSocket error:', msg)
					return
				}
				
				// Check if this is a tick message or direct data
				const data = msg.type === 'tick' ? msg : msg
				
				// Prefer alias mapping, else derive using option fields
				const sym = String(data.symbol || '')
				const alias = sym.includes('|') ? sym : null
				// Filter ticks not matching the selected expiry
				if (selectedExpiry) {
					let tickExpRaw = String(data.expiry_date || '')
					if ((!tickExpRaw || tickExpRaw.length < 9) && alias) {
						const ap = alias.split('|')
						if (ap.length >= 2) tickExpRaw = ap[1]
					}
					let isoTickExp = tickExpRaw
					// Convert 'DD-Mon-YYYY' to 'YYYY-MM-DD', or keep ISO
					if (tickExpRaw && tickExpRaw.includes('-') && tickExpRaw.split('-').length === 3 && tickExpRaw.length >= 9 && tickExpRaw.length <= 20) {
						const parts = tickExpRaw.split('-')
						if (parts[1] && parts[1].length === 3) {
							const [dd, mon, yyyy] = parts
							const months = { Jan:'01',Feb:'02',Mar:'03',Apr:'04',May:'05',Jun:'06',Jul:'07',Aug:'08',Sep:'09',Oct:'10',Nov:'11',Dec:'12' }
							if (months[mon]) isoTickExp = `${yyyy}-${months[mon]}-${dd}`
						}
					}
					const selDate = selectedExpiry.slice(0,10)
					if (isoTickExp && isoTickExp.slice(0,10) !== selDate) {
						return
					}
				}
				let side, strike
				if (alias && aliasToSideStrike.current.has(alias)) {
					({ side, strike } = aliasToSideStrike.current.get(alias))
				} else if (alias) {
					const parts = alias.split('|')
					if (parts.length >= 4) {
						side = parts[2] === 'CALL' ? 'call' : 'put'
						strike = Number(parts[3])
					}
				}
				if (!side) {
					if (data?.strike_price && (data?.right || data?.right_type)) {
						strike = Number(data.strike_price)
						const rt = String(data.right || data.right_type).toUpperCase()
						side = rt === 'CE' || rt === 'CALL' ? 'call' : 'put'
					} else {
						return
					}
				}
				
				// Prefer ltp (often a string) then last/close
				let ltp = null
				if (data.ltp !== undefined && data.ltp !== null && !Number.isNaN(Number(data.ltp))) {
					ltp = Number(data.ltp)
				} else if (data.last !== undefined && data.last !== null && !Number.isNaN(Number(data.last))) {
					ltp = Number(data.last)
				} else if (data.close !== undefined && data.close !== null && !Number.isNaN(Number(data.close))) {
					ltp = Number(data.close)
				}
				if (ltp == null) {
					return
				}
				
				// Extract volume and OI from WebSocket fields
				let volume = null
				let openInterest = null
				let changePct = null
				
				// Get volume from multiple possible fields (strings or numbers)
				if (data.volume !== undefined && data.volume !== null && !Number.isNaN(Number(data.volume))) {
					volume = Number(data.volume)
				} else if (data.ltq !== undefined && data.ltq !== null && !Number.isNaN(Number(data.ltq))) {
					volume = Number(data.ltq)
				} else if (data.total_quantity_traded !== undefined && data.total_quantity_traded !== null && !Number.isNaN(Number(data.total_quantity_traded))) {
					volume = Number(data.total_quantity_traded)
				}
				
				// Get Open Interest from multiple possible fields (strings or numbers)
				if (data.open_interest !== undefined && data.open_interest !== null && !Number.isNaN(Number(data.open_interest))) {
					openInterest = Number(data.open_interest)
				} else if (data.OI !== undefined && data.OI !== null && !Number.isNaN(Number(data.OI))) {
					openInterest = Number(data.OI)
				} else if (data.oi !== undefined && data.oi !== null && !Number.isNaN(Number(data.oi))) {
					openInterest = Number(data.oi)
				}
				
				// Also try ttv field for OI (Total Trade Volume = OI in crores)
				if (openInterest === null && data.ttv) {
					const ttvStr = String(data.ttv)
					const oiMatch = ttvStr.match(/^([\d.]+)([KMB]?)$/i)
					if (oiMatch) {
						let oiValue = parseFloat(oiMatch[1])
						const unit = oiMatch[2].toUpperCase()
						// Convert to actual OI based on unit
						if (unit === 'K') oiValue *= 1000
						else if (unit === 'M') oiValue *= 1000000
						else if (unit === 'B' || unit === 'C') oiValue *= 10000000 // Crores
						openInterest = Math.round(oiValue)
					}
				}
				
				// Parse change percent (string or number)
				if (data.change_pct !== undefined && data.change_pct !== null && !Number.isNaN(Number(data.change_pct))) {
					changePct = Number(data.change_pct)
				} else if (data.change !== undefined && data.change !== null && !Number.isNaN(Number(data.change))) {
					changePct = Number(data.change)
				} else if (data.close !== undefined && data.close !== null && !Number.isNaN(Number(data.close))) {
					const closeNum = Number(data.close)
					if (closeNum > 0 && ltp !== null) {
						changePct = ((ltp - closeNum) / closeNum) * 100
					}
				}
				
				// Tiny visual throttle with flash (up/down color) without losing ticks
				const key = `${side}:${Math.round(Number(strike))}`
				pendingMiniRef.current.set(key, { side, strike: Number(strike), ltp, volume, openInterest, changePct })
				if (!miniTimerRef.current) {
					miniTimerRef.current = setTimeout(() => {
						miniTimerRef.current = null
						const staged = Array.from(pendingMiniRef.current.values())
						pendingMiniRef.current.clear()
						setOptionData((prev) => {
							const next = { ...prev }
							for (const u of staged) {
								const k = `${u.side}:${Math.round(Number(u.strike))}`
								const prevLtp = lastLtpRef.current.get(k)
								lastLtpRef.current.set(k, u.ltp)
								if (typeof prevLtp === 'number') {
									flashRef.current.set(k, u.ltp > prevLtp ? 'up' : (u.ltp < prevLtp ? 'down' : null))
								}
								const list = u.side === 'call' ? [...(next.calls || [])] : [...(next.puts || [])]
								const target = Math.round(Number(u.strike))
								let idx = list.findIndex((r) => Math.round(Number(r.strike_price)) === target)
								if (idx < 0) {
									list.push({
										strike_price: Number(u.strike),
										last_price: u.ltp,
										ltp: u.ltp,
										volume: (typeof u.volume === 'number' && u.volume > 0) ? u.volume : 0,
										open_interest: (typeof u.openInterest === 'number' && u.openInterest > 0) ? u.openInterest : 0,
										oi: (typeof u.openInterest === 'number' && u.openInterest > 0) ? u.openInterest : 0,
										change_pct: (typeof u.changePct === 'number') ? u.changePct : null
									})
								} else {
									const updates = { ltp: u.ltp, last_price: u.ltp, last: u.ltp }
									if (u.volume !== null && u.volume !== undefined) { updates.volume = u.volume; updates.ltq = u.volume }
									if (u.openInterest !== null && u.openInterest !== undefined) { updates.open_interest = u.openInterest; updates.oi = u.openInterest; updates.OI = u.openInterest }
									if (u.changePct !== null && u.changePct !== undefined) { updates.change_pct = u.changePct }
									list[idx] = { ...list[idx], ...updates }
								}
								if (u.side === 'call') next.calls = list; else next.puts = list
							}
							setFlashTick((t) => t + 1)
							return next
						})
					}, visualThrottleMs)
				}
			} catch (err) {
				console.error('Error parsing WebSocket message:', err)
			}
		}
		ws.onerror = () => {}
		ws.onclose = () => { wsRef.current = null; tokenSubscribed.current = false }
		return () => { try { ws.close() } catch {} }
	}, [isVisible])

	const loadExpiryDates = async () => {
		try {
			const response = await fetch(`${apiBase}/api/option-chain/expiry-dates?index=${indexConfig.symbol}`)
			const data = await response.json()
			if (data.success) {
				setExpiryDates(data.dates || [])
				// Only set a default if user hasn't chosen one yet
				if ((!selectedExpiry || selectedExpiry === '') && data.dates && data.dates.length > 0) {
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
		setLoading(true)
		setError('')
		
		try {
			// Build query params: selected expiry and optional underlying price hint
			const params = new URLSearchParams()
			if (selectedExpiry) params.set('expiry_date', selectedExpiry)
			if (realUnderlyingPrice) params.set(`${indexConfig.symbol.toLowerCase()}_price`, String(realUnderlyingPrice))
			const qs = params.toString() ? `?${params.toString()}` : ''
			const response = await fetch(`${apiBase}${indexConfig.apiEndpoint}${qs}`)
			const data = await response.json()
			
			if (data.success) {
				// Temporarily set raw data; will prune to ATM below
				setOptionData({
					calls: data.calls || [],
					puts: data.puts || [],
					underlying: data.underlying,
					expiry_date: data.expiry_date
				})
				setLastUpdate(new Date())
				
				// Ensure we have an expiry selected before subscribing
				if ((!selectedExpiry || selectedExpiry === '') && data.expiry_date) {
					setSelectedExpiry(data.expiry_date)
				}
				
				// Update underlying price if available (use real price if provided, otherwise use API data)
				if (realUnderlyingPrice) {
					setUnderlyingPrice({
						last_price: realUnderlyingPrice,
						close: realUnderlyingPrice
					})
				} else if (data.underlying_price) {
					setUnderlyingPrice({
						last_price: data.underlying_price,
						close: data.underlying_price
					})
				}
				// Build alias map for WS mapping: UNDER|EXPIRY|RIGHT|STRIKE
				aliasToSideStrike.current.clear()
				const underlyingVal = (realUnderlyingPrice || data.underlying_price || 0)
				const findAtm = (arr) => {
					if (!Array.isArray(arr) || arr.length === 0) return null
					let best = arr[0]
					let bestDiff = Math.abs(Number(best.strike_price) - underlyingVal)
					for (const r of arr) {
						const d = Math.abs(Number(r.strike_price) - underlyingVal)
						if (d < bestDiff) { best = r; bestDiff = d }
					}
					return best
				}
				const atmCall = findAtm(data.calls || [])
				const atmPut = findAtm(data.puts || [])
				const atmStrike = atmCall?.strike_price ?? atmPut?.strike_price
				const base = Math.round(Number(atmStrike))
				const step = 50
				const desired = [base - 150, base - 100, base - 50, base, base + 50, base + 100, base + 150]
				const pickByStrikes = (arr) => {
					const out = []
					for (const s of desired) {
						const found = (arr || []).find(r => Math.round(Number(r.strike_price)) === s)
						if (found) out.push(found); else out.push({ strike_price: s, ltp: null, last_price: null, volume: 0, open_interest: 0, oi: 0 })
					}
					return out
				}
				const callsNear = pickByStrikes(data.calls || [])
				const putsNear = pickByStrikes(data.puts || [])
				// Preserve last known values when replacing dataset
				setOptionData((prev) => {
					const preserve = (newRows, prevRows) => {
						const out = []
						for (const r of newRows) {
							const prevMatch = (prevRows || []).find(p => Math.round(Number(p.strike_price)) === Math.round(Number(r.strike_price)))
							if (prevMatch) {
								out.push({
									...r,
									ltp: (typeof prevMatch.ltp === 'number' && prevMatch.ltp > 0) ? prevMatch.ltp : r.ltp,
									last_price: (typeof prevMatch.last_price === 'number' && prevMatch.last_price > 0) ? prevMatch.last_price : r.last_price,
									volume: (typeof prevMatch.volume === 'number' && prevMatch.volume > 0) ? prevMatch.volume : (r.volume ?? 0),
									open_interest: (typeof prevMatch.open_interest === 'number' && prevMatch.open_interest > 0) ? prevMatch.open_interest : (r.open_interest ?? 0),
									oi: (typeof prevMatch.oi === 'number' && prevMatch.oi > 0) ? prevMatch.oi : (r.oi ?? r.open_interest ?? 0)
								})
							} else {
								out.push(r)
							}
						}
						return out
					}
					return {
						...prev,
						calls: preserve(callsNear, prev.calls),
						puts: preserve(putsNear, prev.puts)
					}
				});
				// Update alias map for 7 strikes (use selected expiry when available)
				const exp = selectedExpiry || data.expiry_date
				callsNear.forEach((c) => {
					const alias = `${indexConfig.symbol}|${exp}|CALL|${c.strike_price}`
					aliasToSideStrike.current.set(alias, { side: 'call', strike: c.strike_price })
				})
				putsNear.forEach((p) => {
					const alias = `${indexConfig.symbol}|${exp}|PUT|${p.strike_price}`
					aliasToSideStrike.current.set(alias, { side: 'put', strike: p.strike_price })
				})
				// Auto-subscribe after fresh data arrives for this expiry
				if (!didAutoSubscribe && selectedExpiry) {
					trySubscribeOptionChain()
					setDidAutoSubscribe(true)
				}
			} else {
				// Avoid clearing current grid if we already have data; surface soft error
				if (!optionData.calls?.length && !optionData.puts?.length) {
					setError(data.error || 'Failed to load option chain')
				}
			}
		} catch (err) {
			// Avoid flicker: only show error if grid is empty
			if (!optionData.calls?.length && !optionData.puts?.length) {
				setError('Failed to load option chain data')
			}
		} finally {
			setLoading(false)
		}
	}

	function trySubscribeOptionChain() {
		if (!wsRef.current || wsRef.current.readyState !== 1) return
		if (tokenSubscribed.current) return
		
		// Get the current expiry date (prefer selected, fallback to API-provided)
		const currentExpiry = selectedExpiry || optionData.expiry_date
		if (!currentExpiry) {
			console.warn('No expiry date available for subscription')
			// Retry shortly; expiry often arrives right after initial grid load
			setTimeout(() => {
				trySubscribeOptionChain()
			}, 500)
			return
		}
		
		// Get only ATM strike from current data
		const allStrikes = [...new Set([...optionData.calls, ...optionData.puts].map(r => r.strike_price))]
		const currentUnderlying = (underlyingPrice?.last_price || underlyingPrice?.close || 0)
		let atm = null
		let bestDiff = Infinity
		for (const s of allStrikes) {
			const d = Math.abs(Number(s) - Number(currentUnderlying))
			if (d < bestDiff) { atm = s; bestDiff = d }
		}
		let strikes = []
		if (atm != null) {
			const base = Math.round(Number(atm))
			const step = 50
			strikes = [base - 150, base - 100, base - 50, base, base + 50, base + 100, base + 150]
		}
		if (strikes.length === 0) {
			console.warn('No strikes available for subscription')
			return
		}
		
		// Send subscription via WebSocket
		try {
			// Unsubscribe any leftovers then subscribe both sides
			try { wsRef.current.send(JSON.stringify({ action: 'unsubscribe_options' })) } catch {}
			wsRef.current.send(JSON.stringify({
				action: 'subscribe_options',
				underlying: indexConfig.symbol,
				expiry_date: currentExpiry,
				strikes: strikes,
				right: 'call'
			}))
			wsRef.current.send(JSON.stringify({
				action: 'subscribe_options',
				underlying: indexConfig.symbol,
				expiry_date: currentExpiry,
				strikes: strikes,
				right: 'put'
			}))
			
			tokenSubscribed.current = true
			console.log('Option chain subscription sent:', { 
				underlying: indexConfig.symbol, 
				expiry_date: currentExpiry, 
				strikes: strikes.length 
			})
		} catch (error) {
			console.error('Option chain subscription error:', error)
		}
	}

	const formatPrice = (price) => {
		if (typeof price !== 'number' || !(price > 0)) return '--'
		return price.toFixed(2)
	}

	const formatPercent = (value) => {
		if (typeof value !== 'number' || Number.isNaN(value)) return '--'
		return value.toFixed(2)
	}

	const formatVolume = (volume) => {
		if (typeof volume !== 'number' || volume === 0) return '--'
		if (volume >= 10000000) { // 1 Crore
			return (volume / 10000000).toFixed(2) + 'C'
		} else if (volume >= 100000) { // 1 Lakh
			return (volume / 100000).toFixed(2) + 'L'
		} else if (volume >= 1000) { // 1 Thousand
			return (volume / 1000).toFixed(2) + 'K'
		}
		return volume.toLocaleString()
	}

	const getChangeColor = (change) => {
		if (typeof change !== 'number') return 'var(--muted)'
		return change >= 0 ? '#57d38c' : '#ff5c5c'
	}

	const getStrikeColor = (strike, underlying) => {
		if (!underlying || typeof strike !== 'number' || underlying === 0) return 'var(--text)'
		const diff = Math.abs(strike - underlying)
		const percentDiff = (diff / underlying) * 100
		
		if (percentDiff <= 2) return '#fbbf24' // Yellow for ATM
		if (percentDiff <= 5) return '#f59e0b' // Orange for near ATM
		return 'var(--text)' // Default for OTM/ITM
	}

	const isATMStrike = (strike, underlying) => {
		if (!underlying || typeof strike !== 'number') {
			return false
		}
		const diff = Math.abs(strike - underlying)
		// Use configurable ATM threshold
		return diff <= indexConfig.atmThreshold
	}

	const handleStrikeClick = (strike) => {
		setSelectedStrike(selectedStrike === strike ? null : strike)
	}

	// Alignment helpers for numeric columns
	const innerColsTemplate = '88px 88px 64px'
	const numCellStyle = {
		textAlign: 'right',
		fontVariantNumeric: 'tabular-nums',
		fontFeatureSettings: 'tnum'
	}
	const strikeCellStyle = {
		textAlign: 'center',
		display: 'flex',
		alignItems: 'center',
		justifyContent: 'center',
		fontVariantNumeric: 'tabular-nums',
		fontFeatureSettings: 'tnum'
	}

	if (!isVisible) return null

	return createPortal(
		<div className="modal-overlay" style={{
			position: 'fixed',
			top: 0,
			left: 0,
			right: 0,
			bottom: 0,
			backgroundColor: '#000000',
			display: 'flex',
			alignItems: 'center',
			justifyContent: 'center',
			zIndex: 9999,
			opacity: 1,
			isolation: 'isolate'
		}}>
			<div className="modal-content" style={{
				backgroundColor: '#0b0f14',
				border: '2px solid #ffffff',
				borderRadius: '12px',
				width: '95%',
				height: '90%',
				maxWidth: '1200px',
				display: 'flex',
				flexDirection: 'column',
				boxShadow: '0 25px 50px -12px #000000, 0 0 0 1px #ffffff',
				opacity: 1,
				position: 'relative',
				zIndex: 10000,
				isolation: 'isolate'
			}}>
				{/* Header */}
				<div style={{
					padding: '20px',
					borderBottom: '1px solid #ffffff',
					display: 'flex',
					justifyContent: 'space-between',
					alignItems: 'center',
					backgroundColor: '#0b0f14',
					opacity: 1
				}}>
					<div>
						<h2 style={{
							margin: 0,
							fontSize: '24px',
							fontWeight: 'bold',
							color: '#e6e9ef'
						}}>
							{indexConfig.displayName} Option Chain
						</h2>
						{underlyingPrice && (
							<div style={{ marginTop: '8px', display: 'flex', alignItems: 'center', gap: '16px' }}>
								<span style={{ color: '#9aa4b2', fontSize: '14px' }}>
									Underlying: <strong style={{ color: '#e6e9ef' }}>₹{formatPrice(underlyingPrice.last_price || underlyingPrice.close)}</strong>
								</span>
								{lastUpdate && (
									<span style={{
										color: '#9aa4b2',
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
					borderBottom: '1px solid #ffffff',
					display: 'flex',
					gap: '16px',
					alignItems: 'center',
					backgroundColor: '#0b0f14',
					opacity: 1
				}}>
					<div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
						<label style={{ color: '#e6e9ef', fontSize: '14px', fontWeight: '500' }}>
							Expiry Date:
						</label>
						<select
							value={selectedExpiry}
							onChange={(e) => { setSelectedExpiry(e.target.value); setUserSelectedExpiry(true) }}
							style={{
								backgroundColor: '#0f141d',
								border: '1px solid rgba(255, 255, 255, 0.15)',
								borderRadius: '6px',
								padding: '6px 12px',
								color: '#e6e9ef',
								fontSize: '14px',
								minWidth: '150px'
							}}
						>
							{expiryDates.map((date) => (
								<option key={date.iso_date} value={date.iso_date}>
									{date.display}
								</option>
							))}
						</select>
					</div>
				</div>

				{/* Error Message */}
				{error && (
					<div style={{
						margin: '16px 20px',
						padding: '12px 16px',
						backgroundColor: 'rgba(255, 92, 92, 0.15)',
						borderLeft: '4px solid #ff5c5c',
						color: '#ff5c5c',
						fontSize: '14px',
						fontWeight: '500'
					}}>
						{error}
					</div>
				)}

				{/* Option Chain Grid */}
				<div style={{
					flex: 1,
					display: 'flex',
					flexDirection: 'column',
					padding: '20px',
					backgroundColor: '#0b0f14',
					opacity: 1
				}}>
					{/* Fixed Headers */}
					<div style={{
						display: 'grid',
						gridTemplateColumns: '1fr 1px 96px 1px 1fr',
						gap: '0',
						fontSize: '12px',
						minWidth: '920px',
						alignItems: 'stretch',
						backgroundColor: '#0b0f14',
						opacity: 1,
						borderRadius: '8px 8px 0 0',
						overflow: 'hidden',
						position: 'sticky',
						top: 0,
						zIndex: 10
					}}>
						{/* Calls Header with Sub-headers */}
						<div style={{ display: 'flex', flexDirection: 'column' }}>
							<div style={{
								textAlign: 'center',
								fontWeight: 'bold',
								color: '#57d38c',
								padding: '12px 8px',
								backgroundColor: 'rgba(87, 211, 140, 0.15)',
								borderRadius: '8px 0 0 0',
								border: '1px solid rgba(87, 211, 140, 0.2)',
								borderRight: 'none'
							}}>
								CALLS
							</div>
							<div style={{
								display: 'grid',
								gridTemplateColumns: innerColsTemplate,
								gap: '1px',
								padding: '8px 0',
								backgroundColor: 'rgba(87, 211, 140, 0.08)',
								fontSize: '12px',
								color: '#9aa4b2',
								border: '1px solid rgba(87, 211, 140, 0.1)',
								borderRight: 'none',
								borderTop: 'none'
							}}>
								<span style={{ ...numCellStyle, paddingRight: 8, fontSize: '12px' }}>CHG %</span>
								<span style={{ ...numCellStyle, paddingRight: 8, fontSize: '12px' }}>OI</span>
								<span style={{ ...numCellStyle, paddingRight: 8, fontSize: '12px' }}>LTP</span>
							</div>
						</div>
						
						{/* Vertical separator between calls and strike */}
						<div style={{
							backgroundColor: 'rgba(255,255,255,0.1)',
							height: '100%'
						}} />
						
						{/* Strike Price Header */}
						<div style={{
							textAlign: 'center',
							fontWeight: 'bold',
							color: '#e6e9ef',
							padding: '12px 8px',
							backgroundColor: 'rgba(255,255,255,0.08)',
							display: 'flex',
							alignItems: 'center',
							justifyContent: 'center',
							border: '1px solid rgba(255,255,255,0.1)',
							borderLeft: 'none',
							borderRight: 'none'
						}}>
							STRIKE
						</div>
						
						{/* Vertical separator between strike and puts */}
						<div style={{
							backgroundColor: 'rgba(255,255,255,0.1)',
							height: '100%'
						}} />
						
						{/* Puts Header with Sub-headers */}
						<div style={{ display: 'flex', flexDirection: 'column' }}>
							<div style={{
								textAlign: 'center',
								fontWeight: 'bold',
								color: '#ff5c5c',
								padding: '12px 8px',
								backgroundColor: 'rgba(255, 92, 92, 0.15)',
								borderRadius: '0 8px 0 0',
								border: '1px solid rgba(255, 92, 92, 0.2)',
								borderLeft: 'none'
							}}>
								PUTS
							</div>
							<div style={{
								display: 'grid',
								gridTemplateColumns: innerColsTemplate,
								gap: '1px',
								padding: '8px 0',
								backgroundColor: 'rgba(255, 92, 92, 0.08)',
								fontSize: '12px',
								color: '#9aa4b2',
								border: '1px solid rgba(255, 92, 92, 0.1)',
								borderLeft: 'none',
								borderTop: 'none'
							}}>
								<span style={{ ...numCellStyle, paddingRight: 8, fontSize: '12px' }}>LTP</span>
								<span style={{ ...numCellStyle, paddingRight: 8, fontSize: '12px' }}>OI</span>
								<span style={{ ...numCellStyle, paddingRight: 8, fontSize: '12px' }}>CHG %</span>
							</div>
						</div>
					</div>

					{/* Scrollable Data Section */}
					<div style={{
						flex: 1,
						overflow: 'auto',
						backgroundColor: '#0b0f14',
						borderRadius: '0 0 8px 8px',
						border: '1px solid rgba(255,255,255,0.1)',
						borderTop: 'none'
					}}>
						<div style={{
							display: 'grid',
							gridTemplateColumns: '1fr 1px 96px 1px 1fr',
							gap: '0',
							fontSize: '12px',
							minWidth: '920px',
							alignItems: 'stretch',
							backgroundColor: '#0b0f14'
						}}>
							{optionData.calls.length > 0 && optionData.puts.length > 0 ? (
							<>
								{/* Data Rows */}
								{optionData.calls.map((call, index) => {
									const put = optionData.puts[index]
									const currentUnderlying = underlyingPrice?.last_price || underlyingPrice?.close
									return (
										<React.Fragment key={index}>
											{/* Calls Data */}
											<div
												style={{
													display: 'grid',
													gridTemplateColumns: innerColsTemplate,
													gap: '1px',
													backgroundColor: isATMStrike(call.strike_price, currentUnderlying) 
														? 'rgba(251, 191, 36, 0.15)' // Highlight ATM with yellow background
														: 'rgba(255,255,255,0.02)',
													borderRadius: index === optionData.calls.length - 1 ? '0 0 0 8px' : '0',
													padding: '8px 0',
													fontSize: '12px',
													border: isATMStrike(call.strike_price, currentUnderlying)
														? '1px solid rgba(251, 191, 36, 0.3)' // Yellow border for ATM
														: '1px solid rgba(87, 211, 140, 0.1)',
													borderRight: 'none',
													borderTop: 'none'
												}}
											>
												<div style={{ 
													...numCellStyle,
													color: getChangeColor((typeof call.change_pct === 'number' ? call.change_pct : (call.change ?? call.change_percent))),
													paddingRight: 8,
													fontSize: '12px'
												}}>
													{formatPercent((typeof call.change_pct === 'number' ? call.change_pct : (call.change ?? call.change_percent)))}
												</div>
												<div style={{ ...numCellStyle, color: '#9aa4b2', paddingRight: 8, fontSize: '12px' }}>
													{formatVolume(call.open_interest || call.oi)}
												</div>
												{(() => {
													const k = `call:${Math.round(Number(call.strike_price))}`
													const flash = flashRef.current.get(k)
													const bg = flash === 'up' ? 'rgba(87,211,140,0.12)' : (flash === 'down' ? 'rgba(255,92,92,0.12)' : 'transparent')
													return (
														<div style={{ ...numCellStyle, color: '#e6e9ef', paddingRight: 8, fontSize: '12px', backgroundColor: bg }}>
															{formatPrice(call.last_price || call.ltp)}
														</div>
													)
												})()}
											</div>

											{/* Vertical separator between calls and strike */}
											<div style={{
												backgroundColor: 'rgba(255,255,255,0.1)',
												height: '100%'
											}} />

											{/* Strike Price */}
											<div
												onClick={() => handleStrikeClick(call.strike_price)}
												style={{
													...strikeCellStyle,
													fontWeight: 'bold',
													color: isATMStrike(call.strike_price, currentUnderlying) 
														? '#fbbf24' 
														: '#e6e9ef',
													padding: '8px 4px',
													backgroundColor: isATMStrike(call.strike_price, currentUnderlying)
														? 'rgba(251, 191, 36, 0.2)' // Highlight ATM with yellow background
														: selectedStrike === call.strike_price 
															? 'rgba(79, 156, 255, 0.2)' 
															: 'rgba(255,255,255,0.05)',
													cursor: 'pointer',
													borderRadius: selectedStrike === call.strike_price ? '4px' : '0',
													fontSize: '12px',
													border: isATMStrike(call.strike_price, currentUnderlying)
														? '1px solid rgba(251, 191, 36, 0.4)' // Yellow border for ATM
														: '1px solid rgba(255,255,255,0.1)',
													borderLeft: 'none',
													borderRight: 'none',
													borderTop: 'none'
												}}
											>
												{formatPrice(call.strike_price)}
											</div>

											{/* Vertical separator between strike and puts */}
											<div style={{
												backgroundColor: 'rgba(255,255,255,0.1)',
												height: '100%'
											}} />

											{/* Puts Data */}
											<div
												style={{
													display: 'grid',
													gridTemplateColumns: innerColsTemplate,
													gap: '1px',
													backgroundColor: isATMStrike(put.strike_price, currentUnderlying) 
														? 'rgba(251, 191, 36, 0.15)' // Highlight ATM with yellow background
														: 'rgba(255,255,255,0.02)',
													borderRadius: index === optionData.calls.length - 1 ? '0 0 8px 0' : '0',
													padding: '8px 0',
													fontSize: '12px',
													border: isATMStrike(put.strike_price, currentUnderlying)
														? '1px solid rgba(251, 191, 36, 0.3)' // Yellow border for ATM
														: '1px solid rgba(255, 92, 92, 0.1)',
													borderLeft: 'none',
													borderTop: 'none'
												}}
											>
												<div style={{ ...numCellStyle, color: '#e6e9ef', paddingRight: 8, fontSize: '12px' }}>
													{formatPrice(put.last_price || put.ltp)}
												</div>
												<div style={{ ...numCellStyle, color: '#9aa4b2', paddingRight: 8, fontSize: '12px' }}>
													{formatVolume(put.open_interest || put.oi)}
												</div>
												<div style={{ 
													...numCellStyle,
													color: getChangeColor((typeof put.change_pct === 'number' ? put.change_pct : (put.change ?? put.change_percent))),
													paddingRight: 8,
													fontSize: '12px'
												}}>
													{formatPercent((typeof put.change_pct === 'number' ? put.change_pct : (put.change ?? put.change_percent)))}
												</div>
											</div>

											{/* Horizontal separator between rows */}
											{index < optionData.calls.length - 1 && (
												<>
													<div style={{
														height: '1px',
														backgroundColor: 'rgba(255,255,255,0.05)',
														margin: '2px 0',
														gridColumn: '1 / 2'
													}} />
													<div style={{
														height: '1px',
														backgroundColor: 'rgba(255,255,255,0.05)',
														margin: '2px 0',
														gridColumn: '3 / 4'
													}} />
													<div style={{
														height: '1px',
														backgroundColor: 'rgba(255,255,255,0.05)',
														margin: '2px 0',
														gridColumn: '5 / 6'
													}} />
												</>
											)}
										</React.Fragment>
									)
								})}
							</>
						) : (
							<div style={{
								gridColumn: '1 / -1',
								textAlign: 'center',
								padding: '40px',
								color: '#9aa4b2',
								fontSize: '16px',
								fontWeight: '500'
							}}>
								{loading ? 'Loading option chain...' : 'No option data available'}
							</div>
						)}
						</div>
					</div>
				</div>
			</div>
		</div>,
		document.body
	)
}
