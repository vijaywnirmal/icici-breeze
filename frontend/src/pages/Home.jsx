import React, { useEffect, useMemo, useState } from 'react'
import { Card, CardHeader, CardContent } from '../components/ui/Card'
import Button from '../components/ui/Button'
import { useNavigate } from 'react-router-dom'

export default function HomePage() {
	const [firstName, setFirstName] = useState('')
	const [loading, setLoading] = useState(true)
	const [error, setError] = useState('')
	const navigate = useNavigate()
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

	const mainFeatures = [
		{
			title: 'Live Trading',
			description: 'Real-time market data and option chains',
			icon: '📈',
			action: () => navigate('/live-trading'),
			color: 'var(--success)',
			bgColor: 'rgba(16, 185, 129, 0.1)'
		},
		{
			title: 'Backtest Strategy',
			description: 'Test your trading strategies with historical data',
			icon: '🔬',
			action: () => navigate('/backtest'),
			color: 'var(--accent)',
			bgColor: 'rgba(37, 99, 235, 0.1)'
		},
		{
			title: 'Strategy Builder',
			description: 'Build and customize trading strategies',
			icon: '🔧',
			action: () => navigate('/builder'),
			color: 'var(--warning)',
			bgColor: 'rgba(245, 158, 11, 0.1)'
		},
		{
			title: 'View Results',
			description: 'Analyze backtest results and performance',
			icon: '📊',
			action: () => navigate('/results'),
			color: '#8b5cf6',
			bgColor: 'rgba(139, 92, 246, 0.1)'
		}
	]

	const quickLinks = [
		{ title: 'Holidays', path: '/holidays', icon: '📅' },
		{ title: 'Profile', action: () => {/* Profile logic */}, icon: '👤' }
	]

	if (loading) {
		return (
			<div className="content">
				<Card>
					<CardContent>
						<div className="flex items-center justify-center py-12">
							<div className="spinner" style={{ width: '32px', height: '32px' }}></div>
						</div>
					</CardContent>
				</Card>
			</div>
		)
	}

	return (
		<div style={{
			flex: 1,
			padding: 'var(--space-8)',
			background: 'var(--bg)',
			overflow: 'auto'
		}}>
			{/* Header Section */}
			<div style={{
				display: 'flex',
				justifyContent: 'space-between',
				alignItems: 'center',
				marginBottom: 'var(--space-8)'
			}}>
				<div>
					<h1 style={{ 
						color: 'var(--text)', 
						fontFamily: 'var(--font-sans)', 
						fontSize: '32px',
						fontWeight: 700,
						marginBottom: 'var(--space-2)' 
					}}>
						{firstName ? `Welcome back, ${firstName}` : 'Breeze Trading Platform'}
					</h1>
					<p style={{ 
						color: 'var(--text-secondary)', 
						fontFamily: 'var(--font-sans)',
						fontSize: '16px',
						margin: 0
					}}>
						Your comprehensive trading and strategy development platform
					</p>
				</div>
				
				{/* Quick Links */}
				<div style={{ display: 'flex', gap: 'var(--space-3)' }}>
					{quickLinks.map((link, index) => (
						<Button
							key={index}
							variant="secondary"
							size="sm"
							onClick={link.action || (() => navigate(link.path))}
							style={{ width: 'auto', marginTop: 0 }}
						>
							<span style={{ marginRight: 'var(--space-1)' }}>{link.icon}</span>
							{link.title}
						</Button>
					))}
				</div>
			</div>

			{/* Main Features Grid */}
			<div style={{
				display: 'grid',
				gridTemplateColumns: 'repeat(2, 1fr)',
				gap: 'var(--space-6)',
				marginBottom: 'var(--space-8)'
			}}>
				{mainFeatures.map((feature, index) => (
					<Card
						key={index}
						style={{
							cursor: 'pointer',
							minHeight: '180px',
							border: `1px solid ${feature.color}20`,
							background: `linear-gradient(135deg, ${feature.bgColor}, var(--panel))`,
							transition: 'all 0.3s ease'
						}}
						onClick={feature.action}
						onMouseEnter={(e) => {
							e.target.style.transform = 'translateY(-4px)'
							e.target.style.boxShadow = `0 8px 32px ${feature.color}40`
						}}
						onMouseLeave={(e) => {
							e.target.style.transform = 'translateY(0)'
							e.target.style.boxShadow = 'none'
						}}
					>
						<CardContent>
							<div style={{
								display: 'flex',
								flexDirection: 'column',
								height: '100%',
								gap: 'var(--space-4)'
							}}>
								<div style={{
									display: 'flex',
									alignItems: 'center',
									gap: 'var(--space-3)'
								}}>
									<div style={{
										fontSize: '48px',
										lineHeight: 1
									}}>
										{feature.icon}
									</div>
									<div style={{ flex: 1 }}>
										<h2 style={{
											color: 'var(--text)',
											fontFamily: 'var(--font-sans)',
											fontSize: '24px',
											fontWeight: 600,
											marginBottom: 'var(--space-2)',
											margin: 0
										}}>
											{feature.title}
										</h2>
									</div>
								</div>
								<p style={{
									color: 'var(--text-secondary)',
									fontFamily: 'var(--font-sans)',
									fontSize: '16px',
									lineHeight: 1.5,
									margin: 0,
									flex: 1
								}}>
									{feature.description}
								</p>
								<div style={{
									display: 'flex',
									alignItems: 'center',
									justifyContent: 'flex-end'
								}}>
									<Button
										variant="outline"
										size="sm"
										style={{
											width: 'auto',
											marginTop: 0,
											borderColor: feature.color,
											color: feature.color
										}}
									>
										Open →
									</Button>
								</div>
							</div>
						</CardContent>
					</Card>
				))}
			</div>

			{/* Quick Stats Section */}
			<div style={{
				display: 'grid',
				gridTemplateColumns: 'repeat(4, 1fr)',
				gap: 'var(--space-4)'
			}}>
				{[
					{ title: 'Market Status', value: 'Live', color: 'var(--success)' },
					{ title: 'Active Strategies', value: '3', color: 'var(--accent)' },
					{ title: 'Total Backtests', value: '12', color: 'var(--warning)' },
					{ title: 'Success Rate', value: '78%', color: '#8b5cf6' }
				].map((stat, index) => (
					<Card key={index}>
						<CardContent>
							<div style={{ textAlign: 'center', padding: 'var(--space-2)' }}>
								<div style={{
									fontSize: '28px',
									fontWeight: 700,
									color: stat.color,
									fontFamily: 'var(--font-mono)',
									marginBottom: 'var(--space-1)'
								}}>
									{stat.value}
								</div>
								<div style={{
									fontSize: '14px',
									color: 'var(--text-secondary)',
									fontFamily: 'var(--font-sans)'
								}}>
									{stat.title}
								</div>
							</div>
						</CardContent>
					</Card>
				))}
			</div>
		</div>
	)
}
