import React, { useEffect, useMemo, useRef, useState } from 'react'

const WS_PATH = '/ws/ticks'

export default function TickerBar() {
	const [data, setData] = useState({
		ltp: null,
		close: null,
		change_pct: null,
		bid: null,
		ask: null,
		timestamp: null,
		status: 'closed', // 'live' | 'closed'
	})
	const [sensex, setSensex] = useState({ ltp: null, close: null, change_pct: null, timestamp: null, status: 'closed' })
	const [bank, setBank] = useState({ ltp: null, close: null, change_pct: null, timestamp: null, status: 'closed' })

	const apiBase = import.meta.env.VITE_API_BASE_URL || ''
	const wsBase = import.meta.env.VITE_API_BASE_WS || ''
	const httpBase = useMemo(() => (apiBase || 'http://127.0.0.1:8000').replace(/\/$/, ''), [apiBase])
	const wsUrl = useMemo(() => {
		const base = (wsBase || httpBase || '').replace(/\/$/, '')
		// If a full ws(s):// provided, use as-is; else derive from http
		if (base.startsWith('ws://') || base.startsWith('wss://')) return `${base}${WS_PATH}`
		if (base.startsWith('http://')) return `ws://${base.substring('http://'.length)}${WS_PATH}`
		if (base.startsWith('https://')) return `wss://${base.substring('https://'.length)}${WS_PATH}`
		return `ws://127.0.0.1:8000${WS_PATH}`
	}, [httpBase, wsBase])

	const wsRef = useRef(null)
	const retryRef = useRef(0)
	const pollTimer = useRef(null)
	const liveTimer = useRef(null)

	const displayPrice = useMemo(() => {
		if (typeof data.ltp === 'number') return data.ltp
		if (typeof data.close === 'number') return data.close
		return null
	}, [data.ltp, data.close])

	const formatNumber = (num) => {
		if (typeof num !== 'number') return '--'
		try { return num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) } catch { return String(num) }
	}

	const derived = useMemo(() => {
		const price = typeof data.ltp === 'number' ? data.ltp : null
		const prev = typeof data.close === 'number' ? data.close : null
		let change = null
		let pct = null
		if (price !== null && prev !== null && prev !== 0) {
			change = price - prev
			pct = (change / prev) * 100
		}
		// If backend provided pct, prefer it
		if (pct === null && typeof data.change_pct === 'number') pct = data.change_pct
		return { change, pct }
	}, [data.ltp, data.close, data.change_pct])

	const derivedSensex = useMemo(() => {
		const price = typeof sensex.ltp === 'number' ? sensex.ltp : null
		const prev = typeof sensex.close === 'number' ? sensex.close : null
		let change = null
		let pct = null
		if (price !== null && prev !== null && prev !== 0) {
			change = price - prev
			pct = (change / prev) * 100
		}
		if (pct === null && typeof sensex.change_pct === 'number') pct = sensex.change_pct
		return { change, pct }
	}, [sensex.ltp, sensex.close, sensex.change_pct])

	const derivedBank = useMemo(() => {
		const price = typeof bank.ltp === 'number' ? bank.ltp : null
		const prev = typeof bank.close === 'number' ? bank.close : null
		let change = null
		let pct = null
		if (price !== null && prev !== null && prev !== 0) {
			change = price - prev
			pct = (change / prev) * 100
		}
		if (pct === null && typeof bank.change_pct === 'number') pct = bank.change_pct
		return { change, pct }
	}, [bank.ltp, bank.close, bank.change_pct])

	useEffect(() => {
		let closed = false

		// Seed from localStorage so prices persist across refresh
		try {
			const nSaved = JSON.parse(localStorage.getItem('ticker:nifty') || 'null')
			if (nSaved && typeof nSaved === 'object') {
				setData(d => ({ ...d, ...nSaved }))
			}
			const sSaved = JSON.parse(localStorage.getItem('ticker:sensex') || 'null')
			if (sSaved && typeof sSaved === 'object') {
				setSensex(s => ({ ...s, ...sSaved }))
			}
			const bSaved = JSON.parse(localStorage.getItem('ticker:banknifty') || 'null')
			if (bSaved && typeof bSaved === 'object') {
				setBank(b => ({ ...b, ...bSaved }))
			}
		} catch (_) {}

		function scheduleReconnect() {
			const retry = Math.min(30000, 1000 * Math.pow(2, retryRef.current || 0))
			retryRef.current = (retryRef.current || 0) + 1
			clearTimeout(liveTimer.current)
			liveTimer.current = setTimeout(connect, retry)
		}

		async function pollSnapshot() {
			try {
				const [nRes, sRes, bRes] = await Promise.all([
					fetch(`${httpBase}/api/quotes/index?symbol=NIFTY&exchange=NSE`),
					fetch(`${httpBase}/api/quotes/index?symbol=BSESEN&exchange=BSE`),
					fetch(`${httpBase}/api/quotes/index?symbol=CNXBAN&exchange=NSE`),
				])
				const [nJson, sJson, bJson] = await Promise.all([
					nRes.json().catch(() => ({})),
					sRes.json().catch(() => ({})),
					bRes.json().catch(() => ({})),
				])
				if (!closed) {
					// If reset window, clear persisted values and blank out state
					if (nJson && nJson.reset) {
						try { localStorage.removeItem('ticker:nifty') } catch (_) {}
						setData(d => ({
							...d,
							ltp: null,
							close: null,
							change_pct: null,
							bid: null,
							ask: null,
							timestamp: nJson?.timestamp ?? d.timestamp,
							status: nJson?.status || 'closed'
						}))
					} else {
						setData(d => ({
							...d,
							ltp: nJson?.ltp ?? d.ltp,
							close: nJson?.close ?? d.close,
							change_pct: nJson?.change_pct ?? d.change_pct,
							bid: nJson?.bid ?? d.bid,
							ask: nJson?.ask ?? d.ask,
							timestamp: nJson?.timestamp ?? d.timestamp,
							status: nJson?.status || 'closed'
						}))
						// persist
						try { localStorage.setItem('ticker:nifty', JSON.stringify({ ltp: nJson?.ltp ?? undefined, close: nJson?.close ?? undefined, change_pct: nJson?.change_pct ?? undefined, timestamp: nJson?.timestamp ?? undefined, status: nJson?.status || 'closed' })) } catch (_) {}
					}

					if (sJson && sJson.reset) {
						try { localStorage.removeItem('ticker:sensex') } catch (_) {}
						setSensex(s => ({
							...s,
							ltp: null,
							close: null,
							change_pct: null,
							timestamp: sJson?.timestamp ?? s.timestamp,
							status: sJson?.status || 'closed'
						}))
					} else {
						setSensex(s => ({
							...s,
							ltp: sJson?.ltp ?? s.ltp,
							close: sJson?.close ?? s.close,
							change_pct: sJson?.change_pct ?? s.change_pct,
							timestamp: sJson?.timestamp ?? s.timestamp,
							status: sJson?.status || 'closed'
						}))
						try { localStorage.setItem('ticker:sensex', JSON.stringify({ ltp: sJson?.ltp ?? undefined, close: sJson?.close ?? undefined, change_pct: sJson?.change_pct ?? undefined, timestamp: sJson?.timestamp ?? undefined, status: sJson?.status || 'closed' })) } catch (_) {}
					}

					if (bJson && bJson.reset) {
						try { localStorage.removeItem('ticker:banknifty') } catch (_) {}
						setBank(b => ({
							...b,
							ltp: null,
							close: null,
							change_pct: null,
							timestamp: bJson?.timestamp ?? b.timestamp,
							status: bJson?.status || 'closed'
						}))
					} else {
						setBank(b => ({
							...b,
							ltp: bJson?.ltp ?? b.ltp,
							close: bJson?.close ?? b.close,
							change_pct: bJson?.change_pct ?? b.change_pct,
							timestamp: bJson?.timestamp ?? b.timestamp,
							status: bJson?.status || 'closed'
						}))
						try { localStorage.setItem('ticker:banknifty', JSON.stringify({ ltp: bJson?.ltp ?? undefined, close: bJson?.close ?? undefined, change_pct: bJson?.change_pct ?? undefined, timestamp: bJson?.timestamp ?? undefined, status: bJson?.status || 'closed' })) } catch (_) {}
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

		function connect() {
			if (closed) return
			stopPolling()
			// If it's before 09:00 IST and backend indicates reset, avoid starting WS
			// by first polling and returning early.
			// This relies on pollSnapshot having cleared persisted values.
			try {
				const ws = new WebSocket(wsUrl)
				wsRef.current = ws

				ws.onopen = () => {
					retryRef.current = 0
					// fetch a snapshot immediately in case ticks are delayed
					pollSnapshot()
					ws.send(JSON.stringify({ action: 'subscribe', symbol: 'NIFTY', exchange_code: 'NSE', product_type: 'cash' }))
				}

				ws.onmessage = (evt) => {
					try {
						const payload = JSON.parse(evt.data)
						// Only treat real ticks as live; ignore info/error/subscribed, etc.
						if (payload && payload.symbol === 'NIFTY' && (payload.type === 'tick' || typeof payload.ltp === 'number')) {
							setData(d => ({
								...d,
								ltp: payload.ltp ?? d.ltp,
								close: payload.close ?? d.close,
								change_pct: payload.change_pct ?? d.change_pct,
								bid: payload.bid ?? d.bid,
								ask: payload.ask ?? d.ask,
								timestamp: payload.timestamp ?? d.timestamp,
								status: 'live'
							}))
						}
					} catch (_) {
						// ignore malformed messages
					}
				}

				ws.onerror = () => {
					startPollingOnce()
				}
				ws.onclose = () => {
					startPollingOnce()
					scheduleReconnect()
				}
			} catch (_) {
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
					wsRef.current.send(JSON.stringify({ action: 'unsubscribe', symbol: 'NIFTY' }))
				}
				wsRef.current?.close()
			} catch (_) {}
			stopPolling()
			clearTimeout(liveTimer.current)
		}
	}, [httpBase, wsUrl])

	const color = data.change_pct > 0 ? '#57d38c' : data.change_pct < 0 ? '#ff5c5c' : 'var(--text)'
	const colorSensex = derivedSensex.change > 0 ? '#57d38c' : derivedSensex.change < 0 ? '#ff5c5c' : 'var(--text)'
	const colorBank = derivedBank.change > 0 ? '#57d38c' : derivedBank.change < 0 ? '#ff5c5c' : 'var(--text)'

	return (
		<div style={{display:'flex', alignItems:'baseline', background:'rgba(255,255,255,0.04)', border:'1px solid rgba(255,255,255,0.06)', borderRadius:10, padding:'10px 14px', width:'100%'}}>
			<div style={{display:'flex', gap:12, alignItems:'baseline', paddingRight:12}}>
				<div style={{fontWeight:700, letterSpacing:0.4, color:'var(--text)'}}>NIFTY 50</div>
				<div style={{fontSize:20, fontWeight:700, color}}>{formatNumber(displayPrice)}</div>
				{derived.change !== null && (
					<div style={{fontSize:13, color: derived.change >= 0 ? '#57d38c' : '#ff5c5c'}}>
						{formatNumber(Math.abs(derived.change))}
						<span style={{opacity:0.7}}> ({typeof derived.pct === 'number' ? `${derived.pct.toFixed(2)}%` : '--'})</span>
					</div>
				)}
			</div>
			<div style={{width:1, height:22, background:'rgba(255,255,255,0.08)', margin:'0 14px'}} />
			<div style={{display:'flex', gap:12, alignItems:'baseline', paddingLeft:12}}>
				<div style={{fontWeight:700, letterSpacing:0.4, color:'var(--text)'}}>SENSEX</div>
				<div style={{fontSize:20, fontWeight:700, color: colorSensex}}>{formatNumber(typeof sensex.ltp === 'number' ? sensex.ltp : sensex.close)}</div>
				{derivedSensex.change !== null && (
					<div style={{fontSize:13, color: derivedSensex.change >= 0 ? '#57d38c' : '#ff5c5c'}}>
						{formatNumber(Math.abs(derivedSensex.change))}
						<span style={{opacity:0.7}}> ({typeof derivedSensex.pct === 'number' ? `${derivedSensex.pct.toFixed(2)}%` : '--'})</span>
					</div>
				)}
			</div>
			<div style={{width:1, height:22, background:'rgba(255,255,255,0.08)', margin:'0 14px'}} />
			<div style={{display:'flex', gap:12, alignItems:'baseline', paddingLeft:12}}>
				<div style={{fontWeight:700, letterSpacing:0.4, color:'var(--text)'}}>BANKNIFTY</div>
				<div style={{fontSize:20, fontWeight:700, color: colorBank}}>{formatNumber(typeof bank.ltp === 'number' ? bank.ltp : bank.close)}</div>
				{derivedBank.change !== null && (
					<div style={{fontSize:13, color: derivedBank.change >= 0 ? '#57d38c' : '#ff5c5c'}}>
						{formatNumber(Math.abs(derivedBank.change))}
						<span style={{opacity:0.7}}> ({typeof derivedBank.pct === 'number' ? `${derivedBank.pct.toFixed(2)}%` : '--'})</span>
					</div>
				)}
			</div>
		</div>
	)
}
