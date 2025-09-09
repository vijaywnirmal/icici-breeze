import React, { useEffect, useMemo, useState } from 'react'
import { Card, CardHeader, CardContent } from '../components/ui/Card'
import Button from '../components/ui/Button'
import Typography from '../components/ui/Typography'
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
			<div className="content" style={{ width: '100%', maxWidth: '1200px', margin: '0 auto' }}>
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
		<div className="content" style={{
			width: '100%',
			maxWidth: '1200px',
			margin: '0 auto',
			padding: 'var(--space-8)'
		}}>
			{/* Header Section */}
			<div style={{
				display: 'flex',
				justifyContent: 'space-between',
				alignItems: 'center',
				marginBottom: 'var(--space-8)'
			}}>
				<div>
					<Typography variant="h1" style={{ marginBottom: 'var(--space-2)' }}>
						{firstName ? `Welcome back, ${firstName}` : 'Breeze Trading Platform'}
					</Typography>
					<Typography variant="body1" color="secondary" style={{ margin: 0 }}>
						Your comprehensive trading and strategy development platform
					</Typography>
				</div>
				
				{/* Quick Links */}
				<div style={{ display: 'flex', gap: 'var(--space-3)' }}>
					{quickLinks.map((link, index) => (
						<Button
							key={index}
							variant="secondary"
							size="sm"
							onClick={link.action || (() => navigate(link.path))}
							style={{ width: 'auto' }}
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
						variant="elevated"
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
										<Typography variant="h2" style={{ margin: 0 }}>
											{feature.title}
										</Typography>
									</div>
								</div>
								<Typography variant="body1" color="secondary" style={{ flex: 1, margin: 0 }}>
									{feature.description}
								</Typography>
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
					<Card key={index} variant="elevated">
						<CardContent>
							<div style={{ textAlign: 'center', padding: 'var(--space-2)' }}>
								<Typography 
									variant="h2" 
									style={{ 
										color: stat.color,
										fontFamily: 'var(--font-mono)',
										marginBottom: 'var(--space-1)',
										fontSize: '28px'
									}}
								>
									{stat.value}
								</Typography>
								<Typography variant="caption" color="secondary">
									{stat.title}
								</Typography>
							</div>
						</CardContent>
					</Card>
				))}
			</div>
		</div>
	)
}
