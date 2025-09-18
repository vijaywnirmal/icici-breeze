import React, { useEffect, useMemo, useState, useRef } from 'react'
import useWebSocket from '../hooks/useWebSocket'
import { Card, CardHeader, CardContent } from '../components/ui/Card'
import Button from '../components/ui/Button'
import Typography from '../components/ui/Typography'
<<<<<<< HEAD
import { useNavigate } from 'react-router-dom'
import WatchlistWidget from '../components/WatchlistWidget'
=======
import { useRouter } from 'next/router'
>>>>>>> 5c637c62df39be05dea64d026b57124ad9477fe3

export default function HomePage() {
	const [firstName, setFirstName] = useState('')
	const [loading, setLoading] = useState(true)
	const [error, setError] = useState('')
	const [searchTerm, setSearchTerm] = useState('')
	const [watchlist, setWatchlist] = useState([
		{ name: 'RELIANCE' },
		{ name: 'TCS' },
		{ name: 'HDFCBANK' },
		{ name: 'INFY' }
	])
	const [suggestions, setSuggestions] = useState([])
	const [openSuggest, setOpenSuggest] = useState(false)
	const debounceRef = useRef(null)
	const [marketStatus, setMarketStatus] = useState(null)
	const router = useRouter()
	const apiBase = (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_BASE_URL) || (typeof window !== 'undefined' ? '' : '')
	const api = useMemo(() => (apiBase || (typeof window !== 'undefined' ? window.location.origin : '')).replace(/\/$/, ''), [apiBase])

	// Live quotes via WebSocket
	const wsBase = (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_BASE_WS) || ''
	const wsUrl = useMemo(() => {
		const base = (wsBase || apiBase).replace(/\/$/, '')
		if (base.startsWith('ws://') || base.startsWith('wss://')) return `${base}/ws/stocks`
		if (base.startsWith('http://')) return `ws://${base.substring('http://'.length)}/ws/stocks`
		if (base.startsWith('https://')) return `wss://${base.substring('https://'.length)}/ws/stocks`
		return 'ws://127.0.0.1:8000/ws/stocks'
	}, [apiBase, wsBase])
	const { isOpen, subscribe, addMessageListener } = useWebSocket(wsUrl, { autoConnect: true })
	const [livePrices, setLivePrices] = useState({})

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
		// Add a timeout to prevent infinite loading
		const timeout = setTimeout(() => {
			if (!cancelled) setLoading(false)
		}, 3000)
		load()
		return () => { 
			cancelled = true
			clearTimeout(timeout)
		}
	}, [api])

<<<<<<< HEAD
	const mainFeatures = [
		{
			title: 'Backtest Strategy',
			icon: '📊',
			description: 'Test your strategies',
			action: () => navigate('/backtest')
		},
		{
			title: 'Strategy Builder',
			icon: '🔧',
			description: 'Build custom strategies',
			action: () => navigate('/builder')
		},
		{
			title: 'View Results',
			icon: '📋',
			description: 'Analyze performance',
			action: () => navigate('/results')
=======
	// Debounced search suggestions
	useEffect(() => {
		if (debounceRef.current) clearTimeout(debounceRef.current)
		const q = searchTerm.trim()
		if (q.length < 2) {
			setSuggestions([])
			setOpenSuggest(false)
			return
>>>>>>> 5c637c62df39be05dea64d026b57124ad9477fe3
		}
		debounceRef.current = setTimeout(async () => {
			try {
				const base = import.meta.env.VITE_API_BASE_URL || ''
				const apiRoot = (base || '').replace(/\/$/, '')
				const url = new URL(`${apiRoot}/api/instruments/search`)
				url.searchParams.set('q', q)
				url.searchParams.set('limit', '10')
				const res = await fetch(url.toString())
				const data = await res.json().catch(() => ({}))
				if (data?.success && Array.isArray(data.items)) {
					setSuggestions(data.items)
					setOpenSuggest(true)
				} else {
					setSuggestions([])
					setOpenSuggest(false)
				}
			} catch {
				setSuggestions([])
				setOpenSuggest(false)
			}
		}, 200)
		return () => {
			if (debounceRef.current) clearTimeout(debounceRef.current)
		}
	}, [searchTerm])

	// Subscribe to live quotes when watchlist updates
	useEffect(() => {
		if (!isOpen) return
		const symbols = watchlist.map(it => ({
			stock_code: (it.symbol || it.name || '').toUpperCase(),
			token: it.token,
			exchange_code: it.exchange_code || 'NSE',
			product_type: 'cash'
		})).filter(s => s.stock_code)
		if (symbols.length) subscribe(symbols)
	}, [isOpen, watchlist, subscribe])

	// Handle incoming ticks and persist last-known values (seed on load)
	useEffect(() => {
		return addMessageListener((data) => {
			if (data && data.type === 'tick' && data.symbol) {
				const sym = String(data.symbol).toUpperCase()
				const next = {
					ltp: data.ltp,
					change_pct: data.change_pct,
					bid: data.bid,
					ask: data.ask,
					timestamp: data.timestamp
				}
				setLivePrices(prev => ({ ...prev, [sym]: next }))
				try { localStorage.setItem(`ltp:${sym}`, JSON.stringify(next)) } catch {}
			}
		})
	}, [addMessageListener])

	// On mount: load trading_watchlist and seed cached LTPs
	useEffect(() => {
		try {
			const saved = JSON.parse(localStorage.getItem('trading_watchlist') || '[]')
			if (Array.isArray(saved) && saved.length > 0) {
				setWatchlist(saved)
				const seeded = {}
				saved.forEach(item => {
					const sym = (item.symbol || item.name || '').toUpperCase()
					const cache = JSON.parse(localStorage.getItem(`ltp:${sym}`) || 'null')
					if (cache && typeof cache === 'object') seeded[sym] = cache
				})
				if (Object.keys(seeded).length) setLivePrices(prev => ({ ...seeded, ...prev }))
			}
		} catch {}
	}, [])

	// Persist unified trading watchlist
	useEffect(() => {
		try { localStorage.setItem('trading_watchlist', JSON.stringify(watchlist)) } catch {}
	}, [watchlist])

// Features menu moved to header; no local navigation grid here

	if (loading) {
		return (
			<div style={{ width: '100%', maxWidth: '1200px', margin: '0 auto', padding: 'var(--space-8)' }}>
				<Card variant="elevated">
					<CardContent>
						<div style={{
							display: 'flex',
							alignItems: 'center',
							justifyContent: 'center',
							padding: 'var(--space-12)'
						}}>
							<div className="spinner" style={{ width: '32px', height: '32px' }}></div>
						</div>
					</CardContent>
				</Card>
			</div>
		)
	}

	return (
<<<<<<< HEAD
		<div style={{ 
			display: 'grid', 
			gridTemplateColumns: '1fr 400px', 
			gap: '24px', 
			height: '100%',
			minHeight: '600px'
		}}>
			{/* Left Column - Main Features */}
			<div style={{ display: 'flex', flexDirection: 'column' }}>
				{/* Welcome Header */}
				<div style={{ marginBottom: '24px' }}>
					<h1 style={{ 
						color: 'var(--text)', 
						margin: '0 0 8px 0', 
						fontSize: '28px',
						fontWeight: 'bold'
					}}>
						Welcome{firstName ? `, ${firstName}` : ''}! 👋
					</h1>
					<p style={{ 
						color: 'var(--muted)', 
						margin: '0', 
						fontSize: '16px' 
					}}>
						Choose a feature to get started with your trading journey
					</p>
				</div>

				{/* Features Grid */}
				<div className="features-grid" style={{
					display: 'grid',
					gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
					gap: '16px',
					flex: 1
				}}>
					{mainFeatures.map((feature, index) => (
						<Card
							key={index}
							variant="elevated"
							className="feature-card"
							style={{
								cursor: 'pointer',
								minHeight: '120px',
								border: '1px solid rgba(255, 255, 255, 0.1)',
								background: 'rgba(255, 255, 255, 0.02)',
								transition: 'all 0.3s ease',
								backdropFilter: 'blur(10px)',
								display: 'flex',
								flexDirection: 'column'
							}}
							onClick={feature.action}
							onMouseEnter={(e) => {
								e.currentTarget.style.transform = 'translateY(-2px)'
								e.currentTarget.style.boxShadow = '0 8px 25px rgba(0,0,0,0.15)'
								e.currentTarget.style.borderColor = 'rgba(79, 156, 255, 0.3)'
							}}
							onMouseLeave={(e) => {
								e.currentTarget.style.transform = 'translateY(0)'
								e.currentTarget.style.boxShadow = 'none'
								e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.1)'
							}}
						>
							<CardContent style={{ 
								display: 'flex', 
								flexDirection: 'column', 
								height: '100%',
								padding: '20px'
							}}>
								<div style={{
									display: 'flex',
									flexDirection: 'column',
									height: '100%',
									gap: '12px',
									alignItems: 'center',
									textAlign: 'center'
								}}>
									<div style={{
										fontSize: '36px',
										lineHeight: 1,
										marginBottom: '4px'
									}}>
										{feature.icon}
									</div>
									<Typography variant="h3" style={{ 
										margin: '0 0 4px 0', 
										fontSize: '18px', 
										color: '#ffffff',
										fontWeight: 'bold'
									}}>
										{feature.title}
									</Typography>
									<Typography variant="caption" color="secondary" style={{ 
										margin: '0', 
										fontSize: '13px', 
										color: 'rgba(255, 255, 255, 0.7)',
										lineHeight: 1.4
									}}>
										{feature.description}
									</Typography>
								</div>
							</CardContent>
						</Card>
					))}
				</div>
			</div>

			{/* Right Column - Watchlist Widget */}
			<div style={{ 
				display: 'flex', 
				flexDirection: 'column',
				height: '100%'
			}}>
				<Card 
					variant="elevated"
					style={{
						height: '100%',
						border: '1px solid rgba(255, 255, 255, 0.1)',
						background: 'rgba(255, 255, 255, 0.02)',
						backdropFilter: 'blur(10px)',
						display: 'flex',
						flexDirection: 'column'
					}}
				>
					<CardContent style={{ 
						height: '100%', 
						padding: '20px',
						display: 'flex',
						flexDirection: 'column'
					}}>
						<WatchlistWidget />
					</CardContent>
				</Card>
			</div>
=======
		<div className="w-full" style={{ display: 'flex', gap: '16px' }}>
			{/* Features grid removed; menu moved to ticker bar */}
			<div style={{ flex: 1 }} />

			{/* Right-side Watchlist panel anchored under flexlayout__tabset_content */}
			<aside className="flexlayout__tabset_content w-[560px] xl:w-[640px] shrink-0 p-5 rounded-2xl" style={{ background: 'rgba(15,16,20,0.6)', border: '1px solid rgba(255,255,255,0.08)', boxShadow: '0 12px 40px rgba(0,0,0,0.35)', backdropFilter: 'blur(14px)', maxHeight: 'calc(100vh - 110px)', overflow: 'hidden' }}>
				{/* Tabs / Header */}
				<div className="flex items-center gap-5 mb-4">
					<button className="text-[15px] font-semibold px-2 py-1 rounded text-white border-b-2 tracking-wide" style={{ borderColor: 'var(--accent, #4f9cff)' }}>My Watchlist</button>
					<button className="text-[14px] text-muted hover:text-white opacity-80 hover:opacity-100">+ Add watchlist</button>
				</div>

				{/* Search */}
				<div className="relative mb-4">
					<span className="absolute left-3 top-1/2 -translate-y-1/2 opacity-70">
						<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
					</span>
					<input
						placeholder="Search & add items"
						className="w-full bg-[rgba(255,255,255,0.06)] outline-none text-primary py-3 pl-10 pr-12 rounded-xl border border-[rgba(255,255,255,0.12)] focus:border-[rgba(79,156,255,0.6)] focus:ring-2 focus:ring-[rgba(79,156,255,0.18)] transition"
						type="text"
						value={searchTerm}
						onChange={(e) => setSearchTerm(e.target.value)}
						onKeyDown={(e) => {
							if (e.key === 'Enter') {
								const trimmed = searchTerm.trim()
								if (trimmed && !watchlist.some(w => w.name.toUpperCase() === trimmed.toUpperCase())) {
									setWatchlist([{ name: trimmed.toUpperCase() }, ...watchlist])
									setSearchTerm('')
								}
							}
						}}
					/>
					<button className="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-lg hover:bg-[rgba(255,255,255,0.1)]" title="Settings">
						<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09c0 .66.39 1.26 1 1.51.58.24 1.25.11 1.72-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06c-.44.47-.57 1.14-.33 1.72.25.61.85 1 1.51 1H21a2 2 0 1 1 0 4h-.09c-.66 0-1.26.39-1.51 1z"/></svg>
					</button>

					{openSuggest && suggestions.length > 0 && (
						<div className="absolute left-0 right-0 mt-1 rounded-md border border-[var(--border-color)]" style={{ background: 'rgba(20,20,25,0.98)', zIndex: 100, maxHeight: '40vh', overflowY: 'auto' }}>
							{suggestions.map((s, i) => (
								<div
									key={`${s.token}-${i}`}
									className="px-3 py-2 text-[13px] cursor-pointer hover:bg-secondaryHoverOnSurfaceZone truncate"
									onClick={() => {
										const symbol = (s.symbol || s.short_name || s.company_name || '').toUpperCase()
										const displayName = s.company_name || s.short_name || symbol
										if (symbol && !watchlist.some(w => (w.symbol || w.name || '').toUpperCase() === symbol)) {
											setWatchlist([{ name: symbol, displayName, symbol, token: s.token, exchange_code: s.exchange_code || s.exchange || 'NSE' }, ...watchlist])
										}
										setSearchTerm('')
										setOpenSuggest(false)
									}}
								>
									<div className="flex items-center gap-2">
										<span className="font-medium truncate">{s.symbol || s.short_name || s.company_name}</span>
										<span className="text-muted truncate">{s.company_name}</span>
									</div>
							</div>
							))}
						</div>
					)}
				</div>

				{/* Professional Table */}
				<div className="rounded-2xl overflow-hidden border border-[rgba(255,255,255,0.08)]" style={{ background: 'rgba(18,20,25,0.55)' }}>
					{/* Table Header */}
					<div className="px-4 py-3 sticky top-0 bg-[rgba(255,255,255,0.08)]" style={{ zIndex: 1 }}>
						<div className="grid grid-cols-12 gap-4 text-[11px] uppercase tracking-wider text-muted font-medium">
							<div className="col-span-4">Symbol</div>
							<div className="col-span-3 text-right">LTP</div>
							<div className="col-span-2 text-right">Change</div>
							<div className="col-span-2 text-right">Change %</div>
							<div className="col-span-1"></div>
						</div>
					</div>
					
					{/* Table Body */}
					<div className="max-h-[60vh] overflow-y-auto">
						{watchlist.length === 0 && (
							<div className="py-8 text-center text-[13px] text-muted">Start typing to add symbols</div>
						)}
						{watchlist.map((item, idx) => {
							const sym = (item.symbol || item.name || '').toUpperCase()
							const quote = livePrices[sym] || {}
							const ltp = typeof quote.ltp === 'number' ? quote.ltp : null
							const pct = typeof quote.change_pct === 'number' ? quote.change_pct : null
							const change = ltp && pct ? (ltp * pct) / 100 : null
							const isPositive = pct !== null && pct >= 0
							const changeColor = pct === null ? 'rgba(255,255,255,0.6)' : isPositive ? '#00d084' : '#ff4757'
							
							return (
								<div 
									key={idx} 
									className="grid grid-cols-12 gap-4 px-4 py-3 border-b border-[rgba(255,255,255,0.04)] hover:bg-[rgba(255,255,255,0.03)] transition-colors duration-200"
									style={{ backgroundColor: idx % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.015)' }}
								>
									{/* Symbol/Name */}
									<div className="col-span-4 flex flex-col justify-center">
										<div className="text-[13px] font-medium text-white truncate">
											{sym}
										</div>
										{item.displayName && item.displayName !== sym && (
											<div className="text-[11px] text-muted truncate mt-0.5">
												{item.displayName}
											</div>
										)}
									</div>
									
									{/* LTP */}
									<div className="col-span-3 flex items-center justify-end">
										<span className="tabular-nums text-[14px] font-semibold text-white">
											{ltp !== null ? `₹${ltp.toFixed(2)}` : '--'}
										</span>
									</div>
									
									{/* Change (absolute) */}
									<div className="col-span-2 flex items-center justify-end">
										<span 
											className="tabular-nums text-[13px] font-medium"
											style={{ color: changeColor }}
										>
											{change !== null ? `${isPositive ? '+' : ''}${change.toFixed(2)}` : '--'}
										</span>
									</div>
									
									{/* Change % */}
									<div className="col-span-2 flex items-center justify-end">
										<span 
											className="tabular-nums text-[13px] font-medium"
											style={{ color: changeColor }}
										>
											{pct !== null ? `${isPositive ? '+' : ''}${pct.toFixed(2)}%` : '--'}
										</span>
									</div>
									
									{/* Remove Button */}
									<div className="col-span-1 flex items-center justify-center">
										<button 
											className="w-6 h-6 rounded-full hover:bg-[rgba(255,255,255,0.1)] flex items-center justify-center opacity-50 hover:opacity-100 transition-all duration-200"
											onClick={() => setWatchlist(watchlist.filter((_, i) => i !== idx))}
											title="Remove from watchlist"
										>
											<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
												<line x1="18" y1="6" x2="6" y2="18"></line>
												<line x1="6" y1="6" x2="18" y2="18"></line>
											</svg>
										</button>
									</div>
								</div>
							)
						})}
					</div>
				</div>
			</aside>
>>>>>>> 5c637c62df39be05dea64d026b57124ad9477fe3
		</div>
	)
}
