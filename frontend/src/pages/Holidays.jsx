import React, { useEffect, useMemo, useState } from 'react'

export default function HolidaysPage() {
	const [dates, setDates] = useState([])
	const [loading, setLoading] = useState(true)
	const [error, setError] = useState('')
	const [year, setYear] = useState('')
	const [items, setItems] = useState([])

	const apiBase = import.meta.env.VITE_API_BASE_URL || ''
	const api = useMemo(() => (apiBase || '').replace(/\/$/, ''), [apiBase])

	useEffect(() => {
		let cancelled = false
		async function load() {
			setLoading(true)
			setError('')
			try {
				const res = await fetch(`${api}/api/market/holidays`)
				const json = await res.json().catch(() => ({}))
				const arr = Array.isArray(json?.dates) ? json.dates : []
				const list = Array.isArray(json?.items) ? json.items : []
				if (!cancelled) {
					setDates(arr)
					setItems(list)
					const years = Array.from(new Set(arr.map(d => String(d).slice(0,4)))).sort()
					const curr = new Date().getFullYear().toString()
					setYear(years.includes(curr) ? curr : (years[years.length - 1] || curr))
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
		<section className="content card" style={{width:'100%', maxWidth:900}}>
				<h1>Holidays</h1>
				{loading && <div className="message">Loading…</div>}
				{error && <div className="message error">{error}</div>}
				{!loading && !error && (
					<>
						<div style={{display:'flex', gap:8, alignItems:'center', margin:'6px 0 10px'}}>
							<label htmlFor="year" style={{opacity:0.8}}>Year:</label>
							<select id="year" value={year} onChange={(e) => setYear(e.target.value)}>
								{Array.from(new Set(dates.map(d => String(d).slice(0,4)))).sort().map(y => (
									<option key={y} value={y}>{y}</option>
								))}
							</select>
						</div>
						<div style={{overflowX:'auto'}}>
							<table className="table" style={{minWidth:480}}>
								<thead>
									<tr>
										<th style={{textAlign:'left'}}>Date</th>
										<th style={{textAlign:'left'}}>Occasion</th>
										<th style={{textAlign:'left'}}>Weekday</th>
									</tr>
								</thead>
								<tbody>
									{items.filter(it => String(it?.date || '').startsWith(year)).map((it, idx) => {
										const iso = String(it.date)
										const [y, m, d] = iso.split('-')
										const ddmmyyyy = (d && m && y) ? `${d.padStart(2,'0')}/${m.padStart(2,'0')}/${y}` : iso
										const dt = new Date(iso)
										const weekday = !isNaN(dt) ? dt.toLocaleDateString('en-IN', { weekday: 'long' }) : ''
										return (
											<tr key={idx}>
												<td>{ddmmyyyy}</td>
												<td>{it?.name || ''}</td>
												<td>{weekday}</td>
											</tr>
										)
									})}
									{items.filter(it => String(it?.date || '').startsWith(year)).length === 0 && (
										<tr><td colSpan={3} style={{opacity:0.7}}>No holidays found</td></tr>
									)}
								</tbody>
							</table>
						</div>
					</>
				)}
		</section>
	)
}


