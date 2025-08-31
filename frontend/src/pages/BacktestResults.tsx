import React, { useEffect, useMemo, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'

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
				name: 'Temp', description: '', universe: [symbol],
				conditions: [{ indicator: 'RSI', symbol, timeframe: '1d', operator: '<', value: 20 }],
				actions: [{ type: 'trade', signal: 'BUY', instrument: 'OPTION', strike: 'ATM', expiry: 'weekly' }]
			}
			const res = await fetch(`${api}/api/backtest/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
			const j = await res.json().catch(() => ({}))
			if (!res.ok || j?.success === false) throw new Error(j?.message || 'Failed to run')
			const sigs: Signal[] = Array.isArray(j?.signals) ? j.signals : []
			setSignals(sigs)
			// Fake equity curve: cumulative signals count (placeholder). Replace with real PnL-based equity.
			let eq = 100000
			const curve = sigs.map((s, i) => ({ timestamp: s.timestamp, equity: eq += 0 }))
			setEquity(curve)
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
		<div className="content card" style={{width:'100%', maxWidth:1200}}>
			<h1>Backtest Results</h1>
			<div className="grid" style={{gridTemplateColumns:'repeat(5, minmax(160px, 1fr)) auto', gap:8}}>
				<input placeholder="Strategy ID (optional)" value={strategyId} onChange={(e) => setStrategyId(e.target.value)} />
				<input type="text" value={symbol} onChange={(e) => setSymbol(e.target.value)} />
				<input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
				<input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
				<button onClick={run} disabled={loading}>{loading ? 'Loading…' : 'Run'}</button>
			</div>
			{error && <div className="message error" style={{marginTop:12}}>{error}</div>}

			<div className="card" style={{marginTop:16}}>
				<h3>Equity Curve</h3>
				<div style={{width:'100%', height:280}}>
					<ResponsiveContainer>
						<LineChart data={equity} margin={{ left: 12, right: 12, top: 8, bottom: 8 }}>
							<CartesianGrid stroke="#223" strokeDasharray="3 3" />
							<XAxis dataKey="timestamp" hide/>
							<YAxis domain={["auto", "auto"]} />
							<Tooltip />
							<Line type="monotone" dataKey="equity" stroke="#4f9cff" dot={false} strokeWidth={2} />
						</LineChart>
					</ResponsiveContainer>
				</div>
			</div>

			<div className="card" style={{marginTop:16}}>
				<h3>Signals</h3>
				<div style={{overflowX:'auto'}}>
					<table className="table" style={{minWidth:720}}>
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
							{signals.length === 0 && <tr><td colSpan={6} style={{opacity:0.7}}>No signals</td></tr>}
						</tbody>
					</table>
				</div>
			</div>
		</div>
	)
}


