import React, { useEffect, useMemo, useState } from 'react'

export default function HomePage() {
	const [firstName, setFirstName] = useState('')
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
				const sess = sessionStorage.getItem('api_session') || ''
				const url = new URL(`${api}/api/profile`)
				if (sess) url.searchParams.set('api_session', sess)
				const res = await fetch(url.toString())
				const j = await res.json().catch(() => ({}))
				if (!cancelled && j?.success) {
					setFirstName(j?.first_name || '')
				}
			} catch (e) {
				if (!cancelled) setError('')
			} finally {
				if (!cancelled) setLoading(false)
			}
		}
		load()
		return () => { cancelled = true }
	}, [api])

	return (
		<section className="content card" style={{width:'100%', maxWidth:1100}}>
			<h1>{firstName ? `Welcome, ${firstName}!` : 'Home'}</h1>
			<p className="muted" style={{marginTop:8}}>Use the Backtest page from the sidebar to run strategies.</p>
		</section>
	)
}
