import React, { useEffect, useMemo, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { Card, CardHeader, CardContent } from '../components/ui/Card'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import Label from '../components/ui/Label'
import Typography from '../components/ui/Typography'

type Signal = {
	timestamp: string
	type: string
	signal: string
	instrument: string
	strike: string
	expiry: string
	strategy_name?: string
}

type Trade = {
	entry_date?: string
	exit_date?: string
	entry_price?: number
	exit_price?: number
	pnl?: number
	pnl_pct?: number
}

export default function BacktestResults() {
	const [strategyId, setStrategyId] = useState('')
	const [symbol, setSymbol] = useState('NIFTY')
	const [start, setStart] = useState('2024-01-01')
	const [end, setEnd] = useState('2024-02-01')
	const [signals, setSignals] = useState<Signal[]>([])
	const [equity, setEquity] = useState<{ timestamp: string, equity: number }[]>([])
	const [trades, setTrades] = useState<Trade[]>([])
	const [loading, setLoading] = useState(false)
	const [error, setError] = useState('')

	const apiBase = (import.meta as any).env?.VITE_API_BASE_URL || ''
	const api = useMemo(() => (apiBase || '').replace(/\/$/, ''), [apiBase])

	async function run() {
		setLoading(true)
		setError('')
		try {
			const payload: any = { symbol, start_date: start, end_date: end }
			if (strategyId) payload.strategy_id = strategyId
			else payload.strategy = {
				name: `RSI Strategy for ${symbol}`, description: 'RSI-based trading strategy', universe: [symbol],
				conditions: [{ indicator: 'RSI', symbol, timeframe: '1d', operator: '<', value: 20 }],
				actions: [{ type: 'trade', signal: 'BUY', instrument: 'OPTION', strike: 'ATM', expiry: 'weekly' }]
			}
			const res = await fetch(`${api}/api/backtest/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
			const j = await res.json().catch(() => ({}))
			if (!res.ok || j?.success === false) throw new Error(j?.message || 'Failed to run')
			const sigs: Signal[] = Array.isArray(j?.signals) ? j.signals : []
			setSignals(sigs)
			// Calculate real equity curve based on signals and trades
			// For now, set empty equity curve until real PnL calculation is implemented
			setEquity([])
			setTrades([])
		} catch (e: any) {
			setError(e?.message || 'Error')
		} finally {
			setLoading(false)
		}
	}

	useEffect(() => {
		// no auto-run
	}, [])

	return (
		<div className="content" style={{ width: '100%', maxWidth: '1200px', margin: '0 auto' }}>
			{/* Header */}
			<div style={{ marginBottom: 'var(--space-8)' }}>
				<Typography variant="h1">Backtest Results</Typography>
				<Typography variant="body1" color="secondary">
					Test your trading strategies with historical market data
				</Typography>
			</div>

			{/* Configuration Form */}
			<Card variant="elevated" style={{ marginBottom: 'var(--space-8)' }}>
				<CardHeader>
					<Typography variant="h3">Backtest Configuration</Typography>
				</CardHeader>
				<CardContent>
					<div style={{
						display: 'grid',
						gridTemplateColumns: 'repeat(5, 1fr) auto',
						gap: 'var(--space-4)',
						alignItems: 'end'
					}}>
						<div>
							<Label>Strategy ID (optional)</Label>
							<Input 
								placeholder="Enter strategy ID" 
								value={strategyId} 
								onChange={(e) => setStrategyId(e.target.value)} 
							/>
						</div>
						<div>
							<Label>Symbol</Label>
							<Input 
								type="text" 
								value={symbol} 
								onChange={(e) => setSymbol(e.target.value)}
								placeholder="NIFTY"
							/>
						</div>
						<div>
							<Label>Start Date</Label>
							<Input 
								type="date" 
								value={start} 
								onChange={(e) => setStart(e.target.value)} 
							/>
						</div>
						<div>
							<Label>End Date</Label>
							<Input 
								type="date" 
								value={end} 
								onChange={(e) => setEnd(e.target.value)} 
							/>
						</div>
						<Button 
							onClick={run} 
							disabled={loading}
							variant="primary"
							size="lg"
							style={{ height: 'var(--size-md)' }}
						>
							{loading ? 'Loading…' : '🚀 Run Backtest'}
						</Button>
					</div>
					{error && (
						<div style={{
							marginTop: 'var(--space-4)',
							padding: 'var(--space-3)',
							background: 'rgba(239, 68, 68, 0.1)',
							border: '1px solid var(--danger)',
							borderRadius: 'var(--radius)',
							color: 'var(--danger)',
							fontSize: '14px'
						}}>
							{error}
						</div>
					)}
				</CardContent>
			</Card>

			{/* Equity Curve */}
			<Card variant="elevated" style={{ marginBottom: 'var(--space-8)' }}>
				<CardHeader>
					<Typography variant="h3">Equity Curve</Typography>
				</CardHeader>
				<CardContent>
					<div style={{ width: '100%', height: '280px' }}>
						{equity.length > 0 ? (
							<ResponsiveContainer>
								<LineChart data={equity} margin={{ left: 12, right: 12, top: 8, bottom: 8 }}>
									<CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
									<XAxis dataKey="timestamp" hide/>
									<YAxis domain={["auto", "auto"]} />
									<Tooltip />
									<Line type="monotone" dataKey="equity" stroke="var(--accent)" dot={false} strokeWidth={2} />
								</LineChart>
							</ResponsiveContainer>
						) : (
							<div style={{
								display: 'flex',
								alignItems: 'center',
								justifyContent: 'center',
								height: '100%',
								color: 'var(--text-muted)',
								fontSize: '16px'
							}}>
								No equity data available. Run a backtest to see results.
							</div>
						)}
					</div>
				</CardContent>
			</Card>

			{/* Signals Table */}
			<Card variant="elevated">
				<CardHeader>
					<Typography variant="h3">Signals</Typography>
				</CardHeader>
				<CardContent>
					<div style={{ overflowX: 'auto' }}>
						<table className="table" style={{ minWidth: '720px' }}>
							<thead>
								<tr>
									<th>Time</th>
									<th>Type</th>
									<th>Signal</th>
									<th>Instrument</th>
									<th>Strike</th>
									<th>Expiry</th>
								</tr>
							</thead>
							<tbody>
								{signals.map((s, i) => (
									<tr key={i}>
										<td>{new Date(s.timestamp).toLocaleString('en-IN')}</td>
										<td>{s.type}</td>
										<td>{s.signal}</td>
										<td>{s.instrument}</td>
										<td>{s.strike}</td>
										<td>{s.expiry}</td>
									</tr>
								))}
								{signals.length === 0 && (
									<tr>
										<td colSpan={6} style={{ 
											opacity: 0.7, 
											textAlign: 'center', 
											padding: 'var(--space-8)',
											color: 'var(--text-muted)'
										}}>
											No signals generated
										</td>
									</tr>
								)}
							</tbody>
						</table>
					</div>
				</CardContent>
			</Card>
		</div>
	)
}


