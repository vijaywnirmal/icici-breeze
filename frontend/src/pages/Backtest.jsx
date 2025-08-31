import React, { useMemo, useState } from 'react'

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
				user_id: '00000000-0000-0000-0000-000000000001',
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
		<section className="content card" style={{width:'100%', maxWidth:1100}}>
			<h1>Backtest</h1>
			<form onSubmit={onRun} className="grid" style={{gridTemplateColumns:'repeat(6, minmax(120px, 1fr))', gap:12}}>
				<div>
					<label>Symbol</label>
					<input value={symbol} onChange={(e) => setSymbol(e.target.value)} placeholder="NIFTY" />
				</div>
				<div>
					<label>Start</label>
					<input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
				</div>
				<div>
					<label>End</label>
					<input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
				</div>
				<div>
					<label>Fast MA</label>
					<input type="number" min={2} value={fast} onChange={(e) => setFast(Number(e.target.value))} />
				</div>
				<div>
					<label>Slow MA</label>
					<input type="number" min={3} value={slow} onChange={(e) => setSlow(Number(e.target.value))} />
				</div>
				<div>
					<label>Capital (₹)</label>
					<input type="number" min={0} step={1000} value={capital} onChange={(e) => setCapital(Number(e.target.value))} />
				</div>
				<div style={{alignSelf:'end'}}>
					<button type="submit" disabled={loading}>
						{loading ? 'Running…' : 'Run Backtest'}
					</button>
				</div>
			</form>

			{error && <div className="message error" style={{marginTop:12}}>{error}</div>}

			{summary && (
				<div className="card" style={{marginTop:16}}>
					<h3>Summary</h3>
					<div className="grid" style={{gridTemplateColumns:'repeat(4, 1fr)', gap:8}}>
						<div><div className="muted">Trades</div><div style={{fontWeight:600}}>{summary.trades}</div></div>
						<div><div className="muted">Net PnL</div><div style={{fontWeight:600}}>₹ {Number(summary.net_pnl || 0).toFixed(2)}</div></div>
						<div><div className="muted">Return</div><div style={{fontWeight:600}}>{Number(summary.return_pct || 0).toFixed(2)}%</div></div>
						<div><div className="muted">Max DD</div><div style={{fontWeight:600}}>{Number(summary.max_drawdown || 0).toFixed(2)}%</div></div>
					</div>
				</div>
			)}

			<div className="card" style={{marginTop:16}}>
				<h3>Trades {backtestId ? `(ID: ${backtestId})` : ''}</h3>
				<div style={{overflowX:'auto'}}>
					<table className="table" style={{minWidth:720}}>
						<thead>
							<tr>
								<th>#</th>
								<th>Entry</th>
								<th>Exit</th>
								<th>Entry Price</th>
								<th>Exit Price</th>
								<th>PnL</th>
								<th>PnL %</th>
							</tr>
						</thead>
						<tbody>
							{trades.map((t, i) => (
								<tr key={i}>
									<td>{t.trade_no || i+1}</td>
									<td>{t.entry_date ? new Date(t.entry_date).toLocaleDateString('en-IN') : ''}</td>
									<td>{t.exit_date ? new Date(t.exit_date).toLocaleDateString('en-IN') : ''}</td>
									<td>{Number(t.entry_price || 0).toFixed(2)}</td>
									<td>{Number(t.exit_price || 0).toFixed(2)}</td>
									<td>{Number(t.pnl || 0).toFixed(2)}</td>
									<td>{Number(t.pnl_pct || 0).toFixed(2)}%</td>
								</tr>
							))}
							{trades.length === 0 && (
								<tr><td colSpan={7} style={{opacity:0.7}}>No trades</td></tr>
							)}
						</tbody>
					</table>
				</div>
			</div>
		</section>
	)
}


