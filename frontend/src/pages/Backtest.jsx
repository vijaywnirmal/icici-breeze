import React, { useMemo, useState } from 'react'
import { Card, CardHeader, CardContent, CardFooter } from '../components/ui/Card'
import Button from '../components/ui/Button'

export default function BacktestPage() {
	const [symbol, setSymbol] = useState('NIFTY')
	const [start, setStart] = useState('2024-01-01')
	const [end, setEnd] = useState('2024-08-31')
	const [fast, setFast] = useState(20)
	const [slow, setSlow] = useState(50)
	const [capital, setCapital] = useState(100000)
	const [loading, setLoading] = useState(false)
	const [error, setError] = useState('')
	const [summary, setSummary] = useState(null)
	const [backtestId, setBacktestId] = useState('')
	const [trades, setTrades] = useState([])

	const apiBase = import.meta.env.VITE_API_BASE_URL || ''
	const api = useMemo(() => (apiBase || '').replace(/\/$/, ''), [apiBase])

	async function onRun(e) {
		e.preventDefault()
		setLoading(true)
		setError('')
		setSummary(null)
		setTrades([])
		setBacktestId('')
		try {
			const payload = {
				symbol: symbol.trim().toUpperCase(),
				start_date: start,
				end_date: end,
				strategy: 'ma_crossover',
				params: { fast, slow, capital }
			}
			const res = await fetch(`${api}/api/backtests/run`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(payload)
			})
			const json = await res.json().catch(() => ({}))
			if (!res.ok || json?.success === false) {
				throw new Error(json?.message || json?.error || 'Backtest failed')
			}
			setSummary(json?.summary || null)
			setBacktestId(json?.backtest_id || '')

			if (json?.backtest_id) {
				const res2 = await fetch(`${api}/api/backtests/${json.backtest_id}`)
				const j2 = await res2.json().catch(() => ({}))
				const t = Array.isArray(j2?.backtest?.trades) ? j2.backtest.trades : []
				setTrades(t)
			}
		} catch (err) {
			setError(err?.message || 'Something went wrong')
		} finally {
			setLoading(false)
		}
	}

	return (
		<div className="content">
			<div className="mb-8">
				<h1 className="text-3xl font-bold mb-2" style={{ color: 'var(--text)' }}>
					Strategy Backtest
				</h1>
				<p className="text-lg" style={{ color: 'var(--text-secondary)' }}>
					Test your trading strategies with historical market data
				</p>
			</div>

			<Card variant="elevated" className="mb-8">
				<CardHeader>
					<h2 className="text-xl font-semibold" style={{ color: 'var(--text)' }}>
						📊 Backtest Configuration
					</h2>
				</CardHeader>
				<CardContent>
					<form onSubmit={onRun} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
						<div>
							<label htmlFor="symbol">Symbol</label>
							<input 
								id="symbol"
								value={symbol} 
								onChange={(e) => setSymbol(e.target.value)} 
								placeholder="NIFTY" 
							/>
						</div>
						<div>
							<label htmlFor="start">Start Date</label>
							<input 
								id="start"
								type="date" 
								value={start} 
								onChange={(e) => setStart(e.target.value)} 
							/>
						</div>
						<div>
							<label htmlFor="end">End Date</label>
							<input 
								id="end"
								type="date" 
								value={end} 
								onChange={(e) => setEnd(e.target.value)} 
							/>
						</div>
						<div>
							<label htmlFor="fast">Fast MA Period</label>
							<input 
								id="fast"
								type="number" 
								min={2} 
								value={fast} 
								onChange={(e) => setFast(Number(e.target.value))} 
							/>
						</div>
						<div>
							<label htmlFor="slow">Slow MA Period</label>
							<input 
								id="slow"
								type="number" 
								min={3} 
								value={slow} 
								onChange={(e) => setSlow(Number(e.target.value))} 
							/>
						</div>
						<div>
							<label htmlFor="capital">Initial Capital (₹)</label>
							<input 
								id="capital"
								type="number" 
								min={0} 
								step={1000} 
								value={capital} 
								onChange={(e) => setCapital(Number(e.target.value))} 
							/>
						</div>
					</form>
				</CardContent>
				<CardFooter>
					<Button 
						type="submit" 
						onClick={onRun}
						loading={loading}
						variant="primary"
						size="lg"
						style={{ width: 'auto' }}
					>
						{loading ? 'Running Backtest...' : '🚀 Run Backtest'}
					</Button>
				</CardFooter>
			</Card>

			{error && (
				<Card variant="danger" className="mb-8">
					<CardContent>
						<div className="flex items-center space-x-3">
							<div className="text-2xl">⚠️</div>
							<div>
								<h3 className="font-semibold text-red-400">Error</h3>
								<p style={{ color: 'var(--danger)' }}>{error}</p>
							</div>
						</div>
					</CardContent>
				</Card>
			)}

			{summary && (
				<Card variant="success" className="mb-8">
					<CardHeader>
						<h2 className="text-xl font-semibold flex items-center space-x-2" style={{ color: 'var(--text)' }}>
							<span>📈</span>
							<span>Backtest Results</span>
						</h2>
					</CardHeader>
					<CardContent>
						<div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
							<div className="text-center">
								<div className="text-2xl font-bold mb-1" style={{ color: 'var(--success)' }}>
									{summary.trades}
								</div>
								<div className="text-sm" style={{ color: 'var(--text-secondary)' }}>
									Total Trades
								</div>
							</div>
							<div className="text-center">
								<div className="text-2xl font-bold mb-1" style={{ 
									color: Number(summary.net_pnl || 0) >= 0 ? 'var(--success)' : 'var(--danger)' 
								}}>
									₹{Number(summary.net_pnl || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}
								</div>
								<div className="text-sm" style={{ color: 'var(--text-secondary)' }}>
									Net P&L
								</div>
							</div>
							<div className="text-center">
								<div className="text-2xl font-bold mb-1" style={{ 
									color: Number(summary.return_pct || 0) >= 0 ? 'var(--success)' : 'var(--danger)' 
								}}>
									{Number(summary.return_pct || 0).toFixed(2)}%
								</div>
								<div className="text-sm" style={{ color: 'var(--text-secondary)' }}>
									Return
								</div>
							</div>
							<div className="text-center">
								<div className="text-2xl font-bold mb-1" style={{ color: 'var(--warning)' }}>
									{Number(summary.max_drawdown || 0).toFixed(2)}%
								</div>
								<div className="text-sm" style={{ color: 'var(--text-secondary)' }}>
									Max Drawdown
								</div>
							</div>
						</div>
					</CardContent>
				</Card>
			)}

		<Card>
			<CardHeader>
				<h2 className="text-xl font-semibold flex items-center space-x-2" style={{ color: 'var(--text)' }}>
					<span>📋</span>
					<span>Trade History {backtestId && `(ID: ${backtestId})`}</span>
				</h2>
			</CardHeader>
			<CardContent>
				<div className="overflow-x-auto">
					<table className="table w-full">
						<thead>
							<tr style={{ backgroundColor: 'var(--panel-light)' }}>
								<th className="text-left py-3 px-4">#</th>
								<th className="text-left py-3 px-4">Entry Date</th>
								<th className="text-left py-3 px-4">Exit Date</th>
								<th className="text-right py-3 px-4">Entry Price</th>
								<th className="text-right py-3 px-4">Exit Price</th>
								<th className="text-right py-3 px-4">P&L</th>
								<th className="text-right py-3 px-4">P&L %</th>
							</tr>
						</thead>
						<tbody>
							{trades.length > 0 ? trades.map((t, i) => (
								<tr key={i} className="border-t hover:bg-panel-light/50 transition-colors">
									<td className="py-3 px-4 font-medium">{t.trade_no || i+1}</td>
									<td className="py-3 px-4" style={{ color: 'var(--text-secondary)' }}>
										{t.entry_date ? new Date(t.entry_date).toLocaleDateString('en-IN') : ''}
									</td>
									<td className="py-3 px-4" style={{ color: 'var(--text-secondary)' }}>
										{t.exit_date ? new Date(t.exit_date).toLocaleDateString('en-IN') : ''}
									</td>
									<td className="py-3 px-4 text-right font-mono">
										₹{Number(t.entry_price || 0).toFixed(2)}
									</td>
									<td className="py-3 px-4 text-right font-mono">
										₹{Number(t.exit_price || 0).toFixed(2)}
									</td>
									<td className="py-3 px-4 text-right font-mono font-semibold" style={{
										color: Number(t.pnl || 0) >= 0 ? 'var(--success)' : 'var(--danger)'
									}}>
										₹{Number(t.pnl || 0).toFixed(2)}
									</td>
									<td className="py-3 px-4 text-right font-mono font-semibold" style={{
										color: Number(t.pnl_pct || 0) >= 0 ? 'var(--success)' : 'var(--danger)'
									}}>
										{Number(t.pnl_pct || 0).toFixed(2)}%
									</td>
								</tr>
							)) : (
								<tr>
									<td colSpan="7" className="py-8 text-center" style={{ color: 'var(--text-secondary)' }}>
										No trades to display. Run a backtest to see results.
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


