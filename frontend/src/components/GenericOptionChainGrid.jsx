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
	const [loading, setLoading] = useState(true) // Start with loading true
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
	const depthRef = useRef(new Map())
	const [flashTick, setFlashTick] = useState(0)
	const [userSelectedExpiry, setUserSelectedExpiry] = useState(false)
	const [didAutoSubscribe, setDidAutoSubscribe] = useState(false)
	const currentExpiryRef = useRef('')
	const subscriptionIdRef = useRef(0)
	const [depthModal, setDepthModal] = useState({ visible: false, strike: null, side: null, call: null, put: null })
	const [marketStatus, setMarketStatus] = useState(null)
	const [depthDataAvailable, setDepthDataAvailable] = useState(false)

	const apiBase = import.meta.env.VITE_API_BASE_URL || ''

	// Process raw depth data from Breeze API
	const processRawDepthData = (depthData) => {
		try {
			const bids = []
			const asks = []
			
			// Process each depth level (1-5)
			for (let i = 1; i <= 5; i++) {
				const buyRateKey = `BestBuyRate-${i}`
				const buyQtyKey = `BestBuyQty-${i}`
				const sellRateKey = `BestSellRate-${i}`
				const sellQtyKey = `BestSellQty-${i}`
				
				// Find the row that contains this level's data
				for (const row of depthData) {
					if (row[buyRateKey] !== undefined && row[buyQtyKey] !== undefined) {
						bids.push({
							price: parseFloat(row[buyRateKey]) || 0,
							qty: parseFloat(row[buyQtyKey]) || 0
						})
					}
					if (row[sellRateKey] !== undefined && row[sellQtyKey] !== undefined) {
						asks.push({
							price: parseFloat(row[sellRateKey]) || 0,
							qty: parseFloat(row[sellQtyKey]) || 0
						})
					}
				}
			}
			
			// Sort bids (highest first) and asks (lowest first)
			bids.sort((a, b) => b.price - a.price)
			asks.sort((a, b) => a.price - b.price)
			
			return { bids, asks }
		} catch (error) {
			console.error('❌ Error processing raw depth data:', error)
			return { bids: [], asks: [] }
		}
	}

	// Robust date conversion function
	const convertToISODate = (dateStr) => {
		if (!dateStr || typeof dateStr !== 'string') return ''
		
		// Handle ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:mm:ss.sssZ)
		if (dateStr.includes('T') || /^\d{4}-\d{2}-\d{2}/.test(dateStr)) {
			// Extract just the date part (YYYY-MM-DD)
			const datePart = dateStr.slice(0, 10)
			console.log('🔍 convertToISODate:', { input: dateStr, output: datePart })
			return datePart
		}
		
		// Handle DD-Mon-YYYY format
		if (dateStr.includes('-') && dateStr.split('-').length === 3) {
			const parts = dateStr.split('-')
			if (parts.length === 3 && parts[1].length === 3) {
				const [dd, mon, yyyy] = parts
				const months = {
					Jan: '01', Feb: '02', Mar: '03', Apr: '04', May: '05', Jun: '06',
					Jul: '07', Aug: '08', Sep: '09', Oct: '10', Nov: '11', Dec: '12'
				}
				if (months[mon]) {
					return `${yyyy}-${months[mon]}-${dd.padStart(2, '0')}`
				}
			}
		}
		
		// Handle DD/MM/YYYY format
		if (dateStr.includes('/') && dateStr.split('/').length === 3) {
			const parts = dateStr.split('/')
			if (parts.length === 3) {
				const [dd, mm, yyyy] = parts
				return `${yyyy}-${mm.padStart(2, '0')}-${dd.padStart(2, '0')}`
			}
		}
		
		return dateStr.slice(0, 10) // Fallback to first 10 characters
	}

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
			checkMarketStatus()
		}
	}, [isVisible])
	
	// Check market status
	const checkMarketStatus = async () => {
		try {
			const response = await fetch(`${apiBase}/api/market/status`)
			const data = await response.json()
			if (data.success) {
				setMarketStatus(data)
				console.log('📊 Market status:', data)
				
				// Load option prices from API if market is closed
				if (!data.is_open && selectedExpiry) {
					setTimeout(() => {
						loadOptionPricesFromAPI()
					}, 1000) // Small delay to ensure state is updated
				}
			}
		} catch (err) {
			console.error('Failed to check market status:', err)
		}
	}
	
	// Load option prices from API when market is closed
	const loadOptionPricesFromAPI = async () => {
		if (marketStatus?.is_open) {
			console.log('📊 Market is open, skipping API price load')
			return
		}
		
		console.log('📊 Market is closed, loading option prices from API...')
		try {
			// Try to get option prices from Breeze API
			const response = await fetch(`${apiBase}/api/option-chain/subscribe?stock_code=${indexConfig.symbol}&expiry_date=${selectedExpiry}&right=both&exchange_code=NFO&product_type=options`)
			const data = await response.json()
			
			if (data.success) {
				console.log('📊 Option prices loaded from API:', data)
				// The API response will trigger websocket updates if available
			}
		} catch (err) {
			console.error('❌ Failed to load option prices from API:', err)
		}
	}

	// Load option chain when component becomes visible or expiry changes
	useEffect(() => {
		if (isVisible && selectedExpiry) {
			console.log('🔄 Expiry changed to:', selectedExpiry)
			console.log('🔄 Raw selectedExpiry type:', typeof selectedExpiry, 'value:', selectedExpiry)
			
			// Update current expiry ref and increment subscription ID immediately
			currentExpiryRef.current = selectedExpiry
			subscriptionIdRef.current += 1
			
		// Clear all option data and reset state completely FIRST
		// But keep the underlying price to prevent blank screen
		const currentUnderlying = optionData.underlying || underlyingPrice
		setOptionData({ 
			calls: [], 
			puts: [], 
			underlying: currentUnderlying, 
			expiry_date: selectedExpiry 
		})
			
			// Clear all cached data immediately (but keep depth data for continuity)
			lastLtpRef.current.clear()
			flashRef.current.clear()
			pendingMiniRef.current.clear()
			aliasToSideStrike.current.clear()
			// Note: Not clearing depthRef to preserve market depth data across expiry changes
			
			// Reset subscription flags
			tokenSubscribed.current = false
			setDidAutoSubscribe(false)
			
			// Unsubscribe previous option subscriptions (if any)
			try {
				if (wsRef.current && wsRef.current.readyState === 1) {
					wsRef.current.send(JSON.stringify({ action: 'unsubscribe_options' }))
					console.log('📤 Sent unsubscribe message for previous expiry')
					
					// Listen for unsubscribe confirmation
					const handleUnsubscribeResponse = (event) => {
						const data = JSON.parse(event.data)
						if (data.type === 'unsubscribed') {
							console.log('✅ Unsubscribe confirmed:', data.message)
							wsRef.current.removeEventListener('message', handleUnsubscribeResponse)
						}
					}
					wsRef.current.addEventListener('message', handleUnsubscribeResponse)
				}
			} catch (e) {
				console.error('❌ Error unsubscribing:', e)
			}
			
			// Load fresh option chain data for the new expiry
			console.log('📥 Loading option chain for expiry:', selectedExpiry)
			loadOptionChain()
			
			// Trigger subscription after a longer delay to ensure unsubscription is processed
			setTimeout(() => {
				console.log('🚀 Triggering immediate subscription for expiry:', selectedExpiry)
				console.log('🔍 Current state before subscription:', {
					tokenSubscribed: tokenSubscribed.current,
					didAutoSubscribe: didAutoSubscribe,
					currentExpiry: currentExpiryRef.current,
					selectedExpiry: selectedExpiry
				})
				trySubscribeOptionChain()
			}, 800)
			
			// Fallback: If no data appears after 3 seconds, try to reload
			setTimeout(() => {
				if (optionData.calls.length === 0 && optionData.puts.length === 0) {
					console.log('⚠️ No data after 3 seconds, attempting reload...')
					loadOptionChain()
				}
			}, 3000)
			
			// Additional fallback: If no websocket data after 5 seconds, try API
			setTimeout(() => {
				if (optionData.calls.length === 0 && optionData.puts.length === 0) {
					console.log('⚠️ No websocket data after 5 seconds, trying API fallback...')
					loadOptionPricesFromAPI()
				}
			}, 5000)
		}
	}, [isVisible, selectedExpiry])

	// WS connect/disconnect lifecycle
	useEffect(() => {
		if (!isVisible) {
			if (wsRef.current) {
				try { wsRef.current.close() } catch {}
				wsRef.current = null
			}
			// Clear depth data when component is not visible
			depthRef.current.clear()
			return
		}
		const wsUrl = (apiBase || '').replace(/^http/, 'ws') + '/ws/options'
		const ws = new WebSocket(wsUrl)
		wsRef.current = ws
		ws.onopen = () => {
			console.log('🔌 Options WebSocket connected')
			// Subscribe immediately if we have context; else retry shortly
			try {
				if (selectedExpiry) {
					console.log('🎯 WebSocket opened with selected expiry:', selectedExpiry)
					// Trigger subscription after a short delay to ensure everything is ready
					setTimeout(() => {
						if (wsRef.current && wsRef.current.readyState === 1) {
							trySubscribeOptionChain()
						}
					}, 300)
				}
			} catch (e) {
				console.error('❌ Error in WebSocket onopen:', e)
			}
		}
		ws.onmessage = (ev) => {
			try {
				const msg = JSON.parse(ev.data)
				console.log('🔍 Options WebSocket message received:', msg)
				
				// Debug market depth data specifically
				if (msg.type === 'tick' && (msg.bids || msg.asks)) {
					console.log('📊 Market Depth Data in WebSocket message:', {
						symbol: msg.symbol,
						bids: msg.bids,
						asks: msg.asks,
						ltp: msg.ltp,
						timestamp: msg.timestamp,
						token: msg.token,
						expiry_date: msg.expiry_date,
						strike_price: msg.strike_price,
						right_type: msg.right_type
					})
					setDepthDataAvailable(true)
				}
				
				// Also check for market depth data in the depth field
				if (msg.type === 'tick' && msg.depth && Array.isArray(msg.depth) && msg.depth.length > 0) {
					console.log('📊 Market Depth Data in depth field:', {
						symbol: msg.symbol,
						depth: msg.depth,
						ltp: msg.ltp,
						timestamp: msg.timestamp,
						token: msg.token
					})
					setDepthDataAvailable(true)
				}
				
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
				// Robust expiry filtering with multiple validation layers
				const currentExpiry = currentExpiryRef.current || selectedExpiry
				if (!currentExpiry) {
					console.log('❌ No current expiry set, ignoring tick')
					return
				}
				
				// Check if this message belongs to the current subscription
				const messageSubscriptionId = data.subscription_id || 0
				const currentSubscriptionId = subscriptionIdRef.current
				if (messageSubscriptionId > 0 && messageSubscriptionId !== currentSubscriptionId) {
					console.log('❌ Message from old subscription, ignoring:', {
						messageId: messageSubscriptionId,
						currentId: currentSubscriptionId
					})
					return
				}
				
				// Extract expiry from multiple possible sources
				let tickExpiry = ''
				
				// Try direct expiry_date field first
				if (data.expiry_date) {
					tickExpiry = convertToISODate(String(data.expiry_date))
				}
				
				// Try alias-based expiry extraction
				if (!tickExpiry && alias) {
					const aliasParts = alias.split('|')
					if (aliasParts.length >= 2) {
						tickExpiry = convertToISODate(aliasParts[1])
					}
				}
				
				// Try symbol-based expiry extraction (fallback)
				if (!tickExpiry && data.symbol && data.symbol.includes('|')) {
					const symbolParts = data.symbol.split('|')
					if (symbolParts.length >= 2) {
						tickExpiry = convertToISODate(symbolParts[1])
					}
				}
				
				// Convert current expiry to comparable format
				const currentExpiryDate = convertToISODate(currentExpiry)
				
				// Debug logging for expiry comparison
				console.log('🔍 Expiry comparison:', {
					rawCurrentExpiry: currentExpiry,
					currentExpiryDate: currentExpiryDate,
					rawTickExpiry: tickExpiry,
					rawSymbol: data.symbol,
					alias: alias,
					expiry_date: data.expiry_date,
					matches: tickExpiry === currentExpiryDate
				})
				
				// Strict expiry validation
				if (!tickExpiry || tickExpiry !== currentExpiryDate) {
					console.log('❌ Expiry mismatch - ignoring tick:', {
						currentExpiry: currentExpiryDate,
						tickExpiry: tickExpiry,
						alias: alias,
						symbol: data.symbol,
						expiry_date: data.expiry_date,
						rawSymbol: data.symbol
					})
					return
				}
				
				// Additional debug logging for successful matches
				console.log('✅ Tick passed expiry validation:', {
					currentExpiry: currentExpiryDate,
					tickExpiry: tickExpiry,
					symbol: data.symbol
				})
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
				// Check for market depth data
				const hasDepth = Array.isArray(data.bids) || Array.isArray(data.asks) || Array.isArray(data.depth) || Array.isArray(data.best_bids) || Array.isArray(data.best_asks)
				
				// Only proceed if we have LTP data OR market depth data
				// This allows price updates even when market depth is not available
				if (ltp == null && !hasDepth) {
					console.log('❌ Skipping tick - no LTP or depth data:', { symbol: data.symbol, ltp, hasDepth })
					return
				}
				
				// Log when we have valid data to process
				if (ltp !== null || hasDepth) {
					console.log('✅ Processing tick data:', { 
						symbol: data.symbol, 
						ltp, 
						hasDepth,
						side,
						strike
					})
				}
				
				// Debug logging for market depth data
				if (hasDepth) {
					console.log('📊 Market Depth Data received:', {
						symbol: data.symbol,
						bids: data.bids,
						asks: data.asks,
						depth: data.depth,
						best_bids: data.best_bids,
						best_asks: data.best_asks
					})
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
				
				// Process market depth data - prioritize the correct format
				let bids = null
				let asks = null
				
				// First check for processed bids/asks arrays
				if (Array.isArray(data.bids) && data.bids.length > 0) {
					bids = data.bids
				} else if (Array.isArray(data.best_bids) && data.best_bids.length > 0) {
					bids = data.best_bids
				} else if (Array.isArray(data.market_depth_buy) && data.market_depth_buy.length > 0) {
					bids = data.market_depth_buy
				}
				
				if (Array.isArray(data.asks) && data.asks.length > 0) {
					asks = data.asks
				} else if (Array.isArray(data.best_asks) && data.best_asks.length > 0) {
					asks = data.best_asks
				} else if (Array.isArray(data.market_depth_sell) && data.market_depth_sell.length > 0) {
					asks = data.market_depth_sell
				}
				
				// If no processed data, try to process the raw depth field
				if ((!bids || !asks) && data.depth && Array.isArray(data.depth) && data.depth.length > 0) {
					console.log('📊 Processing raw depth data:', data.depth)
					const processedDepth = processRawDepthData(data.depth)
					if (processedDepth.bids && processedDepth.bids.length > 0) {
						bids = processedDepth.bids
					}
					if (processedDepth.asks && processedDepth.asks.length > 0) {
						asks = processedDepth.asks
					}
				}
				
				// Tiny visual throttle with flash (up/down color) without losing ticks
				const key = `${side}:${Math.round(Number(strike))}`
				pendingMiniRef.current.set(key, { 
					side, 
					strike: Number(strike), 
					ltp, 
					volume, 
					openInterest, 
					changePct, 
					bids, 
					asks, 
					timestamp: data.timestamp || data.ltt || data.datetime || null 
				})
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
								if (typeof u.ltp === 'number') {
									lastLtpRef.current.set(k, u.ltp)
								}
								try { 
									// Store market depth data if available
									if (u && (u.bids || u.asks)) {
										const depthData = { 
											bids: u.bids || [], 
											asks: u.asks || [], 
											ltp: u.ltp, 
											timestamp: u.timestamp || new Date().toISOString() 
										}
										depthRef.current.set(k, depthData)
										console.log('📊 Storing depth data:', { 
											key: k, 
											depthData, 
											side: u.side, 
											strike: u.strike,
											bidsLength: depthData.bids.length,
											asksLength: depthData.asks.length
										})
										
										// Update depth modal if it's currently open for this strike
										if (depthModal.visible && depthModal.strike === u.strike) {
											const keyCall = `call:${Math.round(Number(u.strike))}`
											const keyPut = `put:${Math.round(Number(u.strike))}`
											const callDepth = depthRef.current.get(keyCall) || { bids: [], asks: [] }
											const putDepth = depthRef.current.get(keyPut) || { bids: [], asks: [] }
											
											setDepthModal(prev => ({
												...prev,
												call: callDepth,
												put: putDepth
											}))
											console.log('📊 Updated depth modal with new data:', { strike: u.strike, callDepth, putDepth })
										}
									} else if (u && u.ltp) {
										// Store LTP data even without depth for continuity
										const depthData = { 
											bids: [], 
											asks: [], 
											ltp: u.ltp, 
											timestamp: u.timestamp || new Date().toISOString() 
										}
										depthRef.current.set(k, depthData)
										console.log('📊 Storing LTP data (no depth):', { 
											key: k, 
											ltp: u.ltp, 
											side: u.side, 
											strike: u.strike
										})
									}
								} catch (err) {
									console.error('❌ Error storing depth data:', err)
								}
								try {
									const exp = currentExpiryRef.current || selectedExpiry || optionData.expiry_date || ''
									const alias = `${indexConfig.symbol}|${exp}|${u.side.toUpperCase()}|${Math.round(Number(u.strike))}`
									localStorage.setItem(`optltp:${alias}`, JSON.stringify({ ltp: u.ltp, timestamp: new Date().toISOString() }))
								} catch (_) {}
								if (typeof prevLtp === 'number') {
									flashRef.current.set(k, u.ltp > prevLtp ? 'up' : (u.ltp < prevLtp ? 'down' : null))
								}
								const list = u.side === 'call' ? [...(next.calls || [])] : [...(next.puts || [])]
								const target = Math.round(Number(u.strike))
								let idx = list.findIndex((r) => Math.round(Number(r.strike_price)) === target)
								if (idx < 0) {
									list.push({
										strike_price: Number(u.strike),
										last_price: (typeof u.ltp === 'number') ? u.ltp : (prevLtp ?? null),
										ltp: (typeof u.ltp === 'number') ? u.ltp : (prevLtp ?? null),
										volume: (typeof u.volume === 'number' && u.volume > 0) ? u.volume : 0,
										open_interest: (typeof u.openInterest === 'number' && u.openInterest > 0) ? u.openInterest : 0,
										oi: (typeof u.openInterest === 'number' && u.openInterest > 0) ? u.openInterest : 0,
										change_pct: (typeof u.changePct === 'number') ? u.changePct : null
									})
								} else {
									const updates = {}
									if (typeof u.ltp === 'number') { updates.ltp = u.ltp; updates.last_price = u.ltp; updates.last = u.ltp }
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
			setLoading(true)
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
		} finally {
			setLoading(false)
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
		console.log('🚀 loadOptionChain called with expiry:', selectedExpiry)
		setLoading(true)
		setError('')
		
		try {
			// Build query params: selected expiry and optional underlying price hint
			const params = new URLSearchParams()
			if (selectedExpiry) params.set('expiry_date', selectedExpiry)
			if (realUnderlyingPrice) params.set(`${indexConfig.symbol.toLowerCase()}_price`, String(realUnderlyingPrice))
			const qs = params.toString() ? `?${params.toString()}` : ''
			const url = `${apiBase}${indexConfig.apiEndpoint}${qs}`
			console.log('📡 Fetching option chain from:', url)
			const response = await fetch(url)
			const data = await response.json()
			console.log('📊 Option chain response:', data)
			
			// If market is closed and we have empty data, try to load from strikes endpoint
			if (data.success && (!data.calls || data.calls.length === 0) && (!data.puts || data.puts.length === 0)) {
				console.log('📊 Empty option chain data, trying to load from strikes endpoint...')
				try {
					const strikesUrl = `${apiBase}/api/option-chain/${indexConfig.symbol.toLowerCase()}-strikes`
					const strikesResponse = await fetch(strikesUrl)
					const strikesData = await strikesResponse.json()
					
					if (strikesData.success && (strikesData.calls || strikesData.puts)) {
						console.log('📊 Loaded option data from strikes endpoint:', strikesData)
						// Merge the strikes data with the original data
						data.calls = strikesData.calls || []
						data.puts = strikesData.puts || []
						data.underlying = strikesData.underlying || data.underlying
						data.underlying_price = strikesData.underlying_price || data.underlying_price
						data.atm_strike = strikesData.atm_strike
						data.strikes = strikesData.strikes
					}
				} catch (strikesError) {
					console.error('❌ Failed to load from strikes endpoint:', strikesError)
				}
			}
			
			if (data.success) {
				// Create initial option data structure with empty strikes
				const currentUnderlying = (underlyingPrice?.last_price || underlyingPrice?.close || indexConfig.defaultPrice || 0)
				let initialStrikes = []
				
				if (indexConfig.symbol === 'NIFTY' || indexConfig.symbol === 'FINNIFTY') {
					const base = Math.round(currentUnderlying / 50) * 50
					initialStrikes = [base - 150, base - 100, base - 50, base, base + 50, base + 100, base + 150]
				} else if (indexConfig.symbol === 'BANKNIFTY') {
					const base = Math.round(currentUnderlying / 100) * 100
					initialStrikes = [base - 300, base - 200, base - 100, base, base + 100, base + 200, base + 300]
				} else {
					const base = Math.round(currentUnderlying / 50) * 50
					initialStrikes = [base - 150, base - 100, base - 50, base, base + 50, base + 100, base + 150]
				}
				
				// Create initial empty option data
				const initialCalls = initialStrikes.map(strike => ({
					strike_price: strike,
					last_price: null,
					ltp: null,
					volume: 0,
					open_interest: 0,
					oi: 0,
					change_pct: null
				}))

				// Seed last-known prices from localStorage if available
				try {
					const exp = data.expiry_date || selectedExpiry || ''
					for (let i = 0; i < initialCalls.length; i++) {
						const s = Math.round(Number(initialCalls[i].strike_price))
						const alias = `${indexConfig.symbol}|${exp}|CALL|${s}`
						const cache = JSON.parse(localStorage.getItem(`optltp:${alias}`) || 'null')
						if (cache && typeof cache.ltp === 'number') {
							initialCalls[i].ltp = cache.ltp
							initialCalls[i].last_price = cache.ltp
						}
					}
				} catch (_) {}
				
				const initialPuts = initialStrikes.map(strike => ({
					strike_price: strike,
					last_price: null,
					ltp: null,
					volume: 0,
					open_interest: 0,
					oi: 0,
					change_pct: null
				}))

				// Seed puts from cache as well
				try {
					const exp = data.expiry_date || selectedExpiry || ''
					for (let i = 0; i < initialPuts.length; i++) {
						const s = Math.round(Number(initialPuts[i].strike_price))
						const alias = `${indexConfig.symbol}|${exp}|PUT|${s}`
						const cache = JSON.parse(localStorage.getItem(`optltp:${alias}`) || 'null')
						if (cache && typeof cache.ltp === 'number') {
							initialPuts[i].ltp = cache.ltp
							initialPuts[i].last_price = cache.ltp
						}
					}
				} catch (_) {}
				
				setOptionData({
					calls: initialCalls,
					puts: initialPuts,
					underlying: data.underlying,
					expiry_date: data.expiry_date
				})
				setLastUpdate(new Date())
				console.log('📊 Created initial option data with strikes:', initialStrikes)
				
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
					// Small delay to ensure data is fully loaded
					setTimeout(() => {
						trySubscribeOptionChain()
						setDidAutoSubscribe(true)
					}, 100)
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

	async function trySubscribeOptionChain() {
		if (!wsRef.current || wsRef.current.readyState !== 1) {
			console.log('❌ WebSocket not ready for subscription')
			return
		}
		if (tokenSubscribed.current) {
			console.log('❌ Already subscribed, skipping')
			return
		}
		
		// Get the current expiry date with strict validation
		const currentExpiry = currentExpiryRef.current || selectedExpiry || optionData.expiry_date
		
		// Check if we're already subscribed to this exact expiry
		if (currentExpiry && optionData.expiry_date === currentExpiry) {
			console.log('❌ Already subscribed to this expiry:', currentExpiry)
			return
		}
		if (!currentExpiry) {
			console.warn('❌ No expiry date available for subscription')
			// Retry shortly; expiry often arrives right after initial grid load
			setTimeout(() => {
				trySubscribeOptionChain()
			}, 500)
			return
		}
		
		// Validate that the expiry hasn't changed since we started this subscription
		if (currentExpiryRef.current && currentExpiryRef.current !== currentExpiry) {
			console.log('❌ Expiry changed during subscription, aborting:', {
				expected: currentExpiryRef.current,
				actual: currentExpiry
			})
			return
		}
		
		// Calculate strikes based on underlying price and index config
		const currentUnderlying = (underlyingPrice?.last_price || underlyingPrice?.close || indexConfig.defaultPrice || 0)
		let strikes = []
		
		if (indexConfig.symbol === 'NIFTY' || indexConfig.symbol === 'FINNIFTY') {
			// 50-point intervals for NIFTY and FINNIFTY
			const base = Math.round(currentUnderlying / 50) * 50
			strikes = [base - 150, base - 100, base - 50, base, base + 50, base + 100, base + 150]
		} else if (indexConfig.symbol === 'BANKNIFTY') {
			// 100-point intervals for BANKNIFTY
			const base = Math.round(currentUnderlying / 100) * 100
			strikes = [base - 300, base - 200, base - 100, base, base + 100, base + 200, base + 300]
		} else {
			// Default to 50-point intervals
			const base = Math.round(currentUnderlying / 50) * 50
			strikes = [base - 150, base - 100, base - 50, base, base + 50, base + 100, base + 150]
		}
		
		console.log('🎯 Calculated strikes for subscription:', {
			strikes: strikes,
			underlying: currentUnderlying,
			expiry: currentExpiry,
			indexConfig: indexConfig.symbol
		})
		
		if (strikes.length === 0) {
			console.warn('❌ No strikes available for subscription')
			return
		}
		
		// Send subscription via WebSocket
		try {
			// Unsubscribe any leftovers then subscribe both sides
			try { 
				wsRef.current.send(JSON.stringify({ action: 'unsubscribe_options' })) 
				console.log('📤 Unsubscribed from previous option subscriptions')
				// Add a small delay to ensure unsubscription is processed
				await new Promise(resolve => setTimeout(resolve, 200))
			} catch (e) {
				console.error('❌ Error unsubscribing:', e)
			}
			
			const subscriptionId = subscriptionIdRef.current
			
			// Subscribe to CALL options
			wsRef.current.send(JSON.stringify({
				action: 'subscribe_options',
				underlying: indexConfig.symbol,
				expiry_date: currentExpiry,
				strikes: strikes,
				right: 'call',
				subscription_id: subscriptionId
			}))
			
			// Subscribe to PUT options
			wsRef.current.send(JSON.stringify({
				action: 'subscribe_options',
				underlying: indexConfig.symbol,
				expiry_date: currentExpiry,
				strikes: strikes,
				right: 'put',
				subscription_id: subscriptionId
			}))
			
			tokenSubscribed.current = true
			console.log('✅ Option chain subscription sent:', {
				underlying: indexConfig.symbol, 
				expiry_date: currentExpiry, 
				strikes: strikes.length,
				strikes_list: strikes,
				subscription_id: subscriptionId
			})
			// Auto-subscribe to market depth for the same strikes
			try {
				await subscribeMarketDepth(strikes)
			} catch {}
		} catch (error) {
			console.error('❌ Option chain subscription error:', error)
		}
	}

	// Subscribe to market depth for specific strikes
	async function subscribeMarketDepth(strikes) {
		if (!wsRef.current || wsRef.current.readyState !== 1) {
			console.log('❌ WebSocket not ready for market depth subscription')
			return
		}
		
		if (!selectedExpiry || !indexConfig?.symbol) {
			console.log('❌ Missing required data for market depth subscription')
			return
		}
		
		console.log('📊 Subscribing to market depth for strikes:', strikes)
		
		try {
			// Subscribe to market depth for CALL options
			wsRef.current.send(JSON.stringify({
				action: 'subscribe_market_depth',
				underlying: indexConfig.symbol,
				expiry_date: selectedExpiry,
				strikes: strikes,
				right: 'call'
			}))
			
			// Subscribe to market depth for PUT options
			wsRef.current.send(JSON.stringify({
				action: 'subscribe_market_depth',
				underlying: indexConfig.symbol,
				expiry_date: selectedExpiry,
				strikes: strikes,
				right: 'put'
			}))
			
			console.log('✅ Market depth subscription sent for strikes:', strikes)
		} catch (error) {
			console.error('❌ Market depth subscription error:', error)
		}
	}

	// Subscribe to market depth for a single strike (when user clicks on it) - side-specific
	const subscribeMarketDepthForStrikeSide = (strike, side) => {
		if (!wsRef.current || wsRef.current.readyState !== 1) {
			return
		}
		if (!selectedExpiry || !indexConfig?.symbol) {
			return
		}
		try {
			wsRef.current.send(JSON.stringify({
				action: 'subscribe_market_depth',
				underlying: indexConfig.symbol,
				expiry_date: selectedExpiry,
				strikes: [strike],
				right: side === 'call' ? 'call' : 'put'
			}))
		} catch {}
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

	const handleStrikeClick = (strike, side) => {
		try {
			setSelectedStrike(strike)
			const keyCall = `call:${Math.round(Number(strike))}`
			const keyPut = `put:${Math.round(Number(strike))}`
			// Use any cached depth immediately (avoid waiting), still subscribe for fresh updates
			const callDepth = side === 'call' ? (depthRef.current.get(keyCall) || { bids: [], asks: [], timestamp: null }) : null
			const putDepth = side === 'put' ? (depthRef.current.get(keyPut) || { bids: [], asks: [], timestamp: null }) : null
			// Subscribe only for this side/strike
			subscribeMarketDepthForStrikeSide(strike, side)
			// Set modal immediately with cached data if present
			setDepthModal({ visible: true, strike, side, call: callDepth, put: putDepth })
			// Retry up to 2 times shortly if no data yet
			let attempts = 0
			const tryAgain = () => {
				attempts += 1
				const hasData = side === 'call' 
					? (depthRef.current.get(keyCall)?.bids?.length > 0)
					: (depthRef.current.get(keyPut)?.asks?.length > 0)
				if (!hasData && attempts < 2) {
					subscribeMarketDepthForStrikeSide(strike, side)
					setTimeout(tryAgain, 1500)
				}
			}
			setTimeout(tryAgain, 1200)
		} catch {}
	}

	const closeDepthModal = () => setDepthModal({ visible: false, strike: null, side: null, call: null, put: null })

	// Alignment helpers for numeric columns
	const innerColsTemplate = '88px 88px 64px'
	const numCellStyle = {
		textAlign: 'center',
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
		<>
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
								{selectedExpiry && (
									<span style={{ 
										color: '#57d38c', 
										fontSize: '14px',
										backgroundColor: 'rgba(87, 211, 140, 0.1)',
										padding: '4px 8px',
										borderRadius: '4px',
										border: '1px solid rgba(87, 211, 140, 0.3)'
									}}>
										📅 Expiry: {new Date(selectedExpiry).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}
									</span>
								)}
								{/* Market Depth Status Indicator */}
								<span style={{
									display: 'flex',
									alignItems: 'center',
									gap: '6px',
									fontSize: '14px',
									padding: '4px 8px',
									borderRadius: '4px',
									background: depthDataAvailable ? 'rgba(87, 211, 140, 0.1)' : 
											   (marketStatus?.is_open ? 'rgba(255, 193, 7, 0.1)' : 'rgba(255, 92, 92, 0.1)'),
									color: depthDataAvailable ? '#57d38c' : 
										   (marketStatus?.is_open ? '#ffc107' : '#ff5c5c'),
									border: `1px solid ${depthDataAvailable ? 'rgba(87, 211, 140, 0.3)' : 
											  (marketStatus?.is_open ? 'rgba(255, 193, 7, 0.3)' : 'rgba(255, 92, 92, 0.3)')}`
								}}>
									<div style={{
										width: '6px',
										height: '6px',
										borderRadius: '50%',
										background: depthDataAvailable ? '#57d38c' : 
												   (marketStatus?.is_open ? '#ffc107' : '#ff5c5c'),
										opacity: depthDataAvailable ? 1 : 0.5
									}}></div>
									{depthDataAvailable ? '📊 Market Depth Live' : 
									 marketStatus?.is_open ? '⏳ Waiting for Depth Data' : '🔒 Market Closed'}
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
					{/* Loading/Empty State */}
					{(loading || !selectedExpiry) && (
						<div style={{ padding: '40px', textAlign: 'center', color: '#9ca3af' }}>
							{!selectedExpiry ? 'Loading expiry dates...' : 'Loading option chain data...'}
						</div>
					)}
					
					{!loading && selectedExpiry && optionData.calls.length === 0 && optionData.puts.length === 0 && (
						<div style={{ padding: '40px', textAlign: 'center', color: '#9ca3af' }}>
							<div>No option data available for selected expiry</div>
							<div style={{ fontSize: '12px', color: '#6b7280', marginTop: '8px' }}>
								Please select a different expiry date
							</div>
						</div>
					)}
					
					{/* Fixed Headers */}
					<div style={{
						display: (!loading && selectedExpiry && (optionData.calls.length > 0 || optionData.puts.length > 0)) ? 'grid' : 'none',
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
								alignItems: 'center',
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
								alignItems: 'center',
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
								{optionData.calls
									.map((call, index) => ({ call, put: optionData.puts[index], originalIndex: index }))
									.filter(({ call, put }) => {
										// Only show rows that have meaningful data
										return call && put && (
											call.ltp > 0 || call.oi > 0 || 
											put.ltp > 0 || put.oi > 0 ||
											call.strike_price || put.strike_price
										)
									})
									.sort((a, b) => {
										// Sort by strike price in ascending order (lowest to highest)
										const strikeA = parseFloat(a.call.strike_price) || 0
										const strikeB = parseFloat(b.call.strike_price) || 0
										return strikeA - strikeB
									})
									.map(({ call, put, originalIndex }, index) => {
									const currentUnderlying = underlyingPrice?.last_price || underlyingPrice?.close
									return (
										<React.Fragment key={originalIndex}>
											{/* Calls Data */}
											<div
												style={{
													display: 'grid',
													gridTemplateColumns: innerColsTemplate,
													gap: '1px',
													alignItems: 'center',
													backgroundColor: isATMStrike(call.strike_price, currentUnderlying) 
														? 'rgba(251, 191, 36, 0.15)' // Highlight ATM with yellow background
														: 'rgba(255,255,255,0.02)',
													borderRadius: index === optionData.calls.length - 1 ? '0 0 0 8px' : '0',
													padding: '8px 0',
													fontSize: '12px',
													border: isATMStrike(call.strike_price, currentUnderlying)
														? '1px solid rgba(251, 191, 36, 0.5)' // Yellow border for ATM
														: '1px solid rgba(87, 211, 140, 0.1)',
													borderRight: isATMStrike(call.strike_price, currentUnderlying) ? '1px solid rgba(251, 191, 36, 0.5)' : 'none',
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
															<div onClick={() => handleStrikeClick(call.strike_price, 'call')} title="View market depth" style={{ ...numCellStyle, color: '#e6e9ef', paddingRight: 8, fontSize: '12px', backgroundColor: bg, cursor: 'pointer', userSelect: 'none' }}>
																{formatPrice(call.last_price || call.ltp)}
															</div>
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
													borderRadius: selectedStrike === call.strike_price ? '4px' : '0',
													fontSize: '12px',
													border: isATMStrike(call.strike_price, currentUnderlying)
														? '1px solid rgba(251, 191, 36, 0.5)' // Yellow border for ATM
														: '1px solid rgba(255,255,255,0.1)',
													borderLeft: isATMStrike(call.strike_price, currentUnderlying) ? '1px solid rgba(251, 191, 36, 0.5)' : 'none',
													borderRight: isATMStrike(call.strike_price, currentUnderlying) ? '1px solid rgba(251, 191, 36, 0.5)' : 'none',
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
													alignItems: 'center',
													backgroundColor: isATMStrike(put.strike_price, currentUnderlying) 
														? 'rgba(251, 191, 36, 0.15)' // Highlight ATM with yellow background
														: 'rgba(255,255,255,0.02)',
													borderRadius: index === optionData.calls.length - 1 ? '0 0 8px 0' : '0',
													padding: '8px 0',
													fontSize: '12px',
													border: isATMStrike(put.strike_price, currentUnderlying)
														? '1px solid rgba(251, 191, 36, 0.5)' // Yellow border for ATM
														: '1px solid rgba(255, 92, 92, 0.1)',
													borderLeft: isATMStrike(put.strike_price, currentUnderlying) ? '1px solid rgba(251, 191, 36, 0.5)' : 'none',
													borderTop: 'none'
												}}
											>
												<div style={{ ...numCellStyle, color: '#e6e9ef', paddingRight: 8, fontSize: '12px' }}>
													<div onClick={() => handleStrikeClick(put.strike_price, 'put')} title="View market depth" style={{ ...numCellStyle, color: '#e6e9ef', paddingRight: 8, fontSize: '12px', cursor: 'pointer', userSelect: 'none' }}>
														{formatPrice(put.last_price || put.ltp)}
													</div>
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
		</div>
		{/* Render depth modal overlay */}
		<DepthModal open={depthModal.visible} onClose={closeDepthModal} strike={depthModal.strike} side={depthModal.side} call={depthModal.call} put={depthModal.put} />
		</>
		,
		document.body
	)
}

// Depth Modal Component
function DepthModal({ open, onClose, strike, side, call, put }) {
	if (!open) return null
	
	// Debug logging for depth modal
	console.log('🔍 DepthModal rendering:', { 
		strike, 
		call, 
		put, 
		callBids: call?.bids, 
		callAsks: call?.asks, 
		putBids: put?.bids, 
		putAsks: put?.asks,
		callBidsLength: call?.bids?.length || 0,
		putAsksLength: put?.asks?.length || 0
	})
	
	// Check if we have any real market depth data
	const hasCallData = call?.bids && Array.isArray(call.bids) && call.bids.length > 0
	const hasPutData = put?.asks && Array.isArray(put.asks) && put.asks.length > 0
	const hasAnyData = side === 'call' ? hasCallData : hasPutData
	
	// Staleness note
	const ts = side === 'call' ? (call?.timestamp || null) : (put?.timestamp || null)
	let freshnessNote = null
	if (ts) {
		try {
			const ageSec = Math.max(0, Math.round((Date.now() - new Date(ts).getTime()) / 1000))
			freshnessNote = `Last updated ${ageSec}s ago`
		} catch {}
	}
	
	const ladderStyle = { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '12px' }
	const box = {
		backgroundColor: '#0f141d', border: '1px solid rgba(255,255,255,0.12)', borderRadius: '8px', padding: '12px'
	}
	const overlay = {
		position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999
	}
	const modal = {
		backgroundColor: '#0b0f14', color: '#e6e9ef', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '10px', padding: '16px', width: 'min(800px, 95vw)'
	}
	
	return (
		<div style={overlay} onClick={onClose}>
			<div style={modal} onClick={(e) => e.stopPropagation()}>
				<div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
					<div style={{ fontWeight: 'bold' }}>Market Depth · {side === 'call' ? 'CALL' : 'PUT'} · Strike {strike}</div>
					<button onClick={onClose} style={{ background: 'transparent', color: '#e6e9ef', border: '1px solid rgba(255,255,255,0.2)', borderRadius: 6, padding: '4px 8px', cursor: 'pointer' }}>Close</button>
				</div>
				{freshnessNote && (
					<div style={{ color: '#9aa4b2', fontSize: '12px', marginBottom: 8 }}>{freshnessNote}</div>
				)}
				
				{!hasAnyData ? (
					<div style={{ 
						textAlign: 'center', 
						padding: '40px', 
						color: '#9aa4b2',
						fontSize: '16px'
					}}>
						<div style={{ marginBottom: '8px' }}>⏳ Waiting for live market depth…</div>
						<div style={{ fontSize: '14px', color: '#6b7280' }}>
							Ensure market is open and the strike is actively trading.
						</div>
					</div>
				) : (
					<div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 16 }}>
						{side === 'call' ? (
							<div style={box}>
								<div style={{ color: '#57d38c', marginBottom: 8, fontWeight: 'bold' }}>CALLS</div>
								{hasCallData ? (
									<div style={ladderStyle}>
										<div style={{ color: '#9aa4b2' }}>Bid Px</div>
										<div style={{ color: '#9aa4b2', textAlign: 'right' }}>Bid Qty</div>
										{call.bids.slice(0, 5).map((r, i) => (
											<React.Fragment key={`cb${i}`}>
												<div>₹{Number(r.price ?? r.bPrice ?? r.bid_price ?? 0).toFixed(2)}</div>
												<div style={{ textAlign: 'right' }}>{Number(r.qty ?? r.bQty ?? r.bid_qty ?? 0).toLocaleString()}</div>
											</React.Fragment>
										))}
									</div>
								) : (
									<div style={{ textAlign: 'center', color: '#6b7280', padding: '20px' }}>
										No call data available
									</div>
								)}
							</div>
						) : (
							<div style={box}>
								<div style={{ color: '#ff5c5c', marginBottom: 8, fontWeight: 'bold' }}>PUTS</div>
								{hasPutData ? (
									<div style={ladderStyle}>
										<div style={{ color: '#9aa4b2' }}>Ask Px</div>
										<div style={{ color: '#9aa4b2', textAlign: 'right' }}>Ask Qty</div>
										{put.asks.slice(0, 5).map((r, i) => (
											<React.Fragment key={`pa${i}`}>
												<div>₹{Number(r.price ?? r.sPrice ?? r.ask_price ?? 0).toFixed(2)}</div>
												<div style={{ textAlign: 'right' }}>{Number(r.qty ?? r.sQty ?? r.ask_qty ?? 0).toLocaleString()}</div>
											</React.Fragment>
										))}
									</div>
								) : (
									<div style={{ textAlign: 'center', color: '#6b7280', padding: '20px' }}>
										No put data available
									</div>
								)}
							</div>
						)}
					</div>
				)}
			</div>
		</div>
	)
}
