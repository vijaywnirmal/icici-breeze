import React, { useEffect, useMemo, useRef, useState } from 'react'

const WS_PATH = '/ws/ticks'

export default function TickerBar() {
	const [data, setData] = useState({
		ltp: null,
		change_pct: null,
		bid: null,
		ask: null,
		timestamp: null,
		status: 'closed', // 'live' | 'closed'
	})

	const apiBase = import.meta.env.VITE_API_BASE_URL || ''
	const wsBase = import.meta.env.VITE_API_BASE_WS || ''
	const httpBase = useMemo(() => (apiBase || '').replace(/\/$/, ''), [apiBase])
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

	useEffect(() => {
		let closed = false

		function scheduleReconnect() {
			const retry = Math.min(30000, 1000 * Math.pow(2, retryRef.current || 0))
			retryRef.current = (retryRef.current || 0) + 1
			clearTimeout(liveTimer.current)
			liveTimer.current = setTimeout(connect, retry)
		}

		async function pollSnapshot() {
			try {
				const res = await fetch(`${httpBase}/api/quotes/index?symbol=NIFTY`)
				const json = await res.json().catch(() => ({}))
				if (!closed) {
					setData(d => ({
						...d,
						ltp: json?.ltp ?? d.ltp,
						change_pct: json?.change_pct ?? d.change_pct,
						bid: json?.bid ?? d.bid,
						ask: json?.ask ?? d.ask,
						timestamp: json?.timestamp ?? d.timestamp,
						status: json?.status || 'closed'
					}))
				}
			} catch (_) {
				// ignore polling errors
			}
		}

		function startPolling() {
			clearInterval(pollTimer.current)
			pollTimer.current = setInterval(pollSnapshot, 45000) // ~45s default
			pollSnapshot()
		}

		function stopPolling() {
			clearInterval(pollTimer.current)
		}

		function connect() {
			if (closed) return
			stopPolling()
			try {
				const ws = new WebSocket(wsUrl)
				wsRef.current = ws

				ws.onopen = () => {
					retryRef.current = 0
					ws.send(JSON.stringify({ action: 'subscribe', symbol: 'NIFTY', exchange_code: 'NSE', product_type: 'cash' }))
				}

				ws.onmessage = (evt) => {
					try {
						const payload = JSON.parse(evt.data)
						if (payload && payload.symbol === 'NIFTY') {
							setData(d => ({
								...d,
								ltp: payload.ltp ?? d.ltp,
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
					startPolling()
				}
				ws.onclose = () => {
					startPolling()
					scheduleReconnect()
				}
			} catch (_) {
				startPolling()
				scheduleReconnect()
			}
		}

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

	return (
		<div style={{display:'flex', gap:12, alignItems:'center', padding:'8px 12px', background:'rgba(255,255,255,0.04)', borderRadius:10}}>
			<div style={{fontWeight:600}}>NIFTY</div>
			<div style={{color}}>{data.ltp ?? '--'}</div>
			<div style={{color}}>{typeof data.change_pct === 'number' ? `${data.change_pct.toFixed(2)}%` : '--'}</div>
			<div style={{color:'var(--muted)'}}>{data.timestamp || ''}</div>
			<div style={{marginLeft:'auto', fontSize:12, padding:'2px 6px', borderRadius:999, background: data.status==='live' ? 'rgba(87,211,140,0.15)' : 'rgba(154,164,178,0.15)', color: data.status==='live' ? '#57d38c' : 'var(--muted)'}}>
				{data.status === 'live' ? 'Live' : 'Closed'}
			</div>
		</div>
	)
}
