import React, { useEffect, useMemo, useState } from 'react'

export default function Home() {
	const [instruments, setInstruments] = useState([])
	const [market, setMarket] = useState(null)
	const [holidays, setHolidays] = useState([])
	const [selectedYear, setSelectedYear] = useState('')
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
				const [instRes, marketRes, holsRes] = await Promise.all([
					fetch(`${api}/api/instruments/status`),
					fetch(`${api}/api/market/status`),
					fetch(`${api}/api/market/holidays`),
				])
				const instJson = await instRes.json().catch(() => ({}))
				const marketJson = await marketRes.json().catch(() => ({}))
				const holsJson = await holsRes.json().catch(() => ({}))
				if (!cancelled) {
					setInstruments(instJson?.indices || [])
					setMarket(marketJson || null)
					const dates = Array.isArray(holsJson?.dates) ? holsJson.dates : []
					setHolidays(dates)
					// default to current year if present in dates
					const years = Array.from(new Set(dates.map(d => String(d).slice(0,4)))).sort()
					const curr = new Date().getFullYear().toString()
					setSelectedYear(years.includes(curr) ? curr : (years[years.length - 1] || curr))
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

					<h2 style={{marginTop: 16, fontSize: 16}}>Trading Holidays</h2>
					<div style={{display:'flex', gap:8, alignItems:'center', margin:'6px 0 10px'}}>
						<label htmlFor="year" style={{opacity:0.8}}>Year:</label>
						<select id="year" value={selectedYear} onChange={(e) => setSelectedYear(e.target.value)}>
							{Array.from(new Set(holidays.map(d => String(d).slice(0,4)))).sort().map(y => (
								<option key={y} value={y}>{y}</option>
							))}
						</select>
					</div>
					<div style={{overflowX:'auto'}}>
						<table className="table" style={{minWidth:360}}>
							<thead>
								<tr>
									<th style={{textAlign:'left'}}>Date</th>
									<th style={{textAlign:'left'}}>Weekday</th>
								</tr>
							</thead>
							<tbody>
								{holidays.filter(d => String(d).startsWith(selectedYear)).sort().map((d, idx) => {
									const dt = new Date(d)
									const weekday = dt.toLocaleDateString('en-IN', { weekday: 'long' })
									return (
										<tr key={idx}>
											<td>{d}</td>
											<td>{weekday}</td>
										</tr>
									)
								})}
								{holidays.filter(d => String(d).startsWith(selectedYear)).length === 0 && (
									<tr><td colSpan={2} style={{opacity:0.7}}>No holidays found</td></tr>
								)}
							</tbody>
						</table>
					</div>
				</>
			)}
		</section>
	)
}
