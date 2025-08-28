import React, { useEffect, useMemo, useRef, useState } from 'react'

export default function Watchlist() {
	const [items, setItems] = useState([])
	const [loading, setLoading] = useState(true)
	const [error, setError] = useState('')

	const apiBase = import.meta.env.VITE_API_BASE_URL || ''
	const httpBase = useMemo(() => (apiBase || '').replace(/\/$/, ''), [apiBase])
	const wsBase = import.meta.env.VITE_API_BASE_WS || ''
	const wsUrl = useMemo(() => {
		const base = (wsBase || httpBase || '').replace(/\/$/, '')
		if (base.startsWith('ws://') || base.startsWith('wss://')) return `${base}/ws/watchlist`
		if (base.startsWith('http://')) return `ws://${base.substring('http://'.length)}/ws/watchlist`
		if (base.startsWith('https://')) return `wss://${base.substring('https://'.length)}/ws/watchlist`
		return 'ws://127.0.0.1:8000/ws/watchlist'
	}, [httpBase, wsBase])

	const wsRef = useRef(null)

	async function load() {
		setLoading(true)
		setError('')
		try {
			const res = await fetch(`${httpBase}/api/watchlist`)
			const json = await res.json().catch(() => ({}))
			if (!res.ok || json.success === false) throw new Error(json?.message || 'Failed to load')
			setItems(json.watchlist?.items || [])
		} catch (err) {
			setError(err?.message || 'Error')
		} finally {
			setLoading(false)
		}
	}

	useEffect(() => {
		load()
	}, [])

	useEffect(() => {
		let closed = false
		try {
			const ws = new WebSocket(wsUrl)
			wsRef.current = ws
			ws.onmessage = (evt) => {
				try {
					const upd = JSON.parse(evt.data)
					if (upd?.symbol) {
						setItems(prev => prev.map(it => it.symbol.toUpperCase() === upd.symbol.toUpperCase() ? ({
							...it,
							last_quote: {
								...(it.last_quote || {}),
								ltp: upd.ltp ?? it.last_quote?.ltp,
								change_pct: upd.change_pct ?? it.last_quote?.change_pct,
								ts: upd.ts ?? it.last_quote?.ts,
							}
						}) : it))
					}
				} catch (_) {}
			}
			ws.onerror = () => {}
			ws.onclose = () => {}
		} catch (_) {}
		return () => {
			closed = true
			try { wsRef.current?.close() } catch (_) {}
		}
	}, [wsUrl])

	async function remove(symbol, exchange_code='NSE', product_type='cash') {
		// Optimistic UI
		setItems(prev => prev.filter(it => !(it.symbol.toUpperCase() === symbol.toUpperCase() && it.exchange_code===exchange_code && it.product_type===product_type)))
		try {
			await fetch(`${httpBase}/api/watchlist/items`, {
				method: 'DELETE', headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ symbol, exchange_code, product_type })
			})
			// Optionally reconcile by reloading
			// await load()
		} catch (_) {}
	}

	return (
		<div style={{display:'flex', flexDirection:'column', gap:8}}>
			{loading && <div className="message">Loading watchlist…</div>}
			{error && <div className="message error">{error}</div>}
			{!loading && items.length === 0 && <div className="message">No items yet</div>}
			{items.map((it, idx) => {
				const cp = it.last_quote?.change_pct
				const color = typeof cp === 'number' ? (cp > 0 ? '#57d38c' : (cp < 0 ? '#ff5c5c' : 'var(--text)')) : 'var(--text)'
				return (
					<div key={idx} style={{display:'flex', gap:12, alignItems:'center', padding:'10px 12px', background:'rgba(255,255,255,0.04)', borderRadius:10}}>
						<div style={{fontWeight:600}}>{it.symbol}</div>
						<div style={{color}}>{it.last_quote?.ltp ?? '--'}</div>
						<div style={{color}}>{typeof cp === 'number' ? `${cp.toFixed(2)}%` : '--'}</div>
						<div style={{color:'var(--muted)'}}>{it.last_quote?.ts || ''}</div>
						<button onClick={() => remove(it.symbol, it.exchange_code, it.product_type)} style={{marginLeft:'auto', width:'auto'}}>⋮ Remove</button>
					</div>
				)
			})}
		</div>
	)
}
