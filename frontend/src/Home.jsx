import React, { useEffect, useMemo, useState } from 'react'

export default function Home() {
	const [instruments, setInstruments] = useState([])
	const [market, setMarket] = useState(null)
	const [loading, setLoading] = useState(true)
	const [error, setError] = useState('')

	const apiBase = import.meta.env.VITE_API_BASE_URL || ''
	const api = useMemo(() => (apiBase || '').replace(/\/$/, ''), [apiBase])


	useEffect(() => {
		let cancelled = false
		async function load() {
			setLoading(true)
			setError('')
			try {
				const [instRes, marketRes] = await Promise.all([
					fetch(`${api}/api/instruments/status`),
					fetch(`${api}/api/market/status`),
				])
				const instJson = await instRes.json().catch(() => ({}))
				const marketJson = await marketRes.json().catch(() => ({}))
				if (!cancelled) {
					setInstruments(instJson?.indices || [])
					setMarket(marketJson || null)
				}
			} catch (err) {
				if (!cancelled) setError(err?.message || 'Failed to load')
			} finally {
				if (!cancelled) setLoading(false)
			}
		}
		load()
		return () => { cancelled = true }
	}, [api])


	return (
		<section className="card">
			<h1>Home</h1>
			{loading && <div className="message">Loading…</div>}
			{error && <div className="message error">{error}</div>}
			{!loading && !error && (
				<>
					<h2 style={{marginTop: 8, fontSize: 16}}>Supported Indices</h2>
					<ul>
						{instruments.map((it, idx) => (
							<li key={idx}>
								{it.display_name} ({it.exchange_code} / {it.product_type})
							</li>
						))}
					</ul>
					<h2 style={{marginTop: 16, fontSize: 16}}>Market Status</h2>
					{market ? (
						<div className="message" style={{color: market.open ? '#57d38c' : 'var(--muted)'}}>
							{market.exchange}: {market.open ? 'Open' : 'Closed'} — {market.server_time}
						</div>
					) : (
						<div className="message">No market data</div>
					)}

				</>
			)}
		</section>
	)
}
