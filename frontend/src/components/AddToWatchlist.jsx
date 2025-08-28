import React, { useMemo, useState } from 'react'

const DEMO = ['NIFTY', 'RELIANCE', 'TCS', 'INFY']

export default function AddToWatchlist({ onAdded }) {
	const [value, setValue] = useState('')
	const [loading, setLoading] = useState(false)
	const [error, setError] = useState('')
	const apiBase = import.meta.env.VITE_API_BASE_URL || ''
	const addUrl = useMemo(() => `${(apiBase || '').replace(/\/$/, '')}/api/watchlist/items`, [apiBase])

	async function onSubmit(e) {
		e.preventDefault()
		setError('')
		const symbol = value.trim().toUpperCase()
		if (!symbol) return
		if (!DEMO.includes(symbol)) {
			setError('Demo accepts NIFTY, RELIANCE, TCS, INFY')
			return
		}
		setLoading(true)
		try {
			const res = await fetch(addUrl, {
				method: 'POST', headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ symbol, exchange_code: 'NSE', product_type: 'cash' })
			})
			const json = await res.json().catch(() => ({}))
			if (!res.ok || json.success === false) throw new Error(json?.message || 'Failed to add')
			onAdded && onAdded(json.watchlist)
			setValue('')
		} catch (err) {
			setError(err?.message || 'Error')
		} finally {
			setLoading(false)
		}
	}

	return (
		<form onSubmit={onSubmit} style={{display:'flex', gap:8, alignItems:'center'}}>
			<input type="text" placeholder="Add symbol (e.g., NIFTY)" value={value} onChange={(e)=>setValue(e.target.value)} style={{flex:1, padding:'10px 12px', borderRadius:10, border:'1px solid rgba(255,255,255,0.08)', background:'#0f141d', color:'var(--text)'}} />
			<button type="submit" disabled={loading} style={{width:'auto'}}>{loading ? 'Adding…' : 'Add'}</button>
			{error && <span className="message error" style={{marginLeft:8}}>{error}</span>}
		</form>
	)
}
