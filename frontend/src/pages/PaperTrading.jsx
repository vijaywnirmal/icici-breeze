import React, { useEffect, useMemo, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid } from 'recharts'
import { Card, CardHeader, CardContent } from '../components/ui/Card'
import Typography from '../components/ui/Typography'

// The paper trader's record (backend/paper): simulated from Breeze history, no orders are ever placed.

const inr = (v, digits = 0) =>
	v == null ? '–' : `${v < 0 ? '−' : ''}₹${Math.abs(Number(v)).toLocaleString('en-IN', { minimumFractionDigits: digits, maximumFractionDigits: digits })}`
const pct = (v) => (v == null ? '–' : `${v > 0 ? '+' : ''}${Number(v).toFixed(2)}%`)
const num = (v, digits = 2) => (v == null ? '–' : Number(v).toFixed(digits))
const tone = (v) => (v > 0 ? 'var(--success)' : v < 0 ? 'var(--danger)' : 'var(--text)')
const hhmm = (iso) => (iso ? iso.slice(11, 16) : '–')
const day = (iso) => (iso ? new Date(`${iso.slice(0, 10)}T00:00:00`).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }) : '–')
const longDay = (iso) => (iso ? new Date(`${iso}T00:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : '–')

const EXIT_LABEL = { target: 'Target', stop: 'Stop', time: 'Square-off' }

function Stat({ label, value, sub, color }) {
	return (
		<div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-4)' }}>
			<div style={{ color: 'var(--text-muted)', fontSize: 12, fontWeight: 500, textTransform: 'uppercase', letterSpacing: 0.5 }}>{label}</div>
			<div style={{ color: color || 'var(--text)', fontSize: 22, fontWeight: 600, marginTop: 4, fontVariantNumeric: 'tabular-nums' }}>{value}</div>
			{sub && <div style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 2 }}>{sub}</div>}
		</div>
	)
}

function Section({ title, aside, children }) {
	return (
		<Card variant="elevated" style={{ marginBottom: 'var(--space-6)' }}>
			<CardHeader>
				<div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 'var(--space-4)', flexWrap: 'wrap' }}>
					<Typography variant="h3" style={{ margin: 0 }}>{title}</Typography>
					{aside}
				</div>
			</CardHeader>
			<CardContent>{children}</CardContent>
		</Card>
	)
}

function Empty({ children }) {
	return <div style={{ color: 'var(--text-muted)', padding: 'var(--space-6) 0', textAlign: 'center' }}>{children}</div>
}

// rows of a backtest report: [label, key, formatter]
const REPORT_ROWS = [
	['Trades', 'trades', (v) => v],
	['Win rate', 'win_rate_pct', (v) => (v == null ? '–' : `${num(v, 1)}%`)],
	['Profit factor', 'profit_factor', (v) => num(v)],
	['Net P&L', 'net_pnl', (v) => inr(v)],
	['Return', 'return_pct', pct],
	['Nifty', 'benchmark_return_pct', pct],
	['Max drawdown', 'max_drawdown_pct', pct],
	['t-stat', 't_stat', (v) => num(v)],
	['Charges', 'charges', (v) => inr(v)],
]

function BacktestReport({ result }) {
	if (result.kind === 'sweep') {
		const keys = Object.keys(result.grid || {})
		return (
			<div style={{ overflowX: 'auto' }}>
				<table className="table" style={{ minWidth: 720, fontVariantNumeric: 'tabular-nums' }}>
					<thead>
						<tr>
							{keys.map((k) => <th key={k}>{k}</th>)}
							<th>In: trades</th><th>In: PF</th><th>In: P&L</th>
							<th>Out: trades</th><th>Out: PF</th><th>Out: P&L</th>
						</tr>
					</thead>
					<tbody>
						{result.rows.slice(0, 10).map((r, i) => (
							<tr key={i}>
								{keys.map((k) => <td key={k}>{r.params[k]}</td>)}
								<td>{r.in_sample?.trades}</td>
								<td>{num(r.in_sample?.profit_factor)}</td>
								<td style={{ color: tone(r.in_sample?.net_pnl) }}>{inr(r.in_sample?.net_pnl)}</td>
								<td>{r.out_of_sample?.trades ?? '–'}</td>
								<td>{num(r.out_of_sample?.profit_factor)}</td>
								<td style={{ color: tone(r.out_of_sample?.net_pnl) }}>{inr(r.out_of_sample?.net_pnl)}</td>
							</tr>
						))}
					</tbody>
				</table>
				<div style={{ color: 'var(--text-muted)', fontSize: 13, marginTop: 'var(--space-3)' }}>
					Ranked on the in-sample period{result.split ? ` (to ${longDay(result.split)})` : ''}; top {Math.min(10, result.rows.length)} of {result.rows.length} settings.
				</div>
			</div>
		)
	}
	const r = result.report || {}
	const cols = [['Overall', r.overall], ['In-sample', r.in_sample], ['Out-of-sample', r.out_of_sample]].filter(([, v]) => v)
	return (
		<div style={{ overflowX: 'auto' }}>
			<table className="table" style={{ minWidth: 480, fontVariantNumeric: 'tabular-nums' }}>
				<thead>
					<tr><th></th>{cols.map(([name]) => <th key={name}>{name}</th>)}</tr>
				</thead>
				<tbody>
					{REPORT_ROWS.map(([label, key, fmt]) => (
						<tr key={key}>
							<td style={{ color: 'var(--text-secondary)' }}>{label}</td>
							{cols.map(([name, seg]) => (
								<td key={name} style={key === 'net_pnl' ? { color: tone(seg[key]) } : undefined}>{fmt(seg[key])}</td>
							))}
						</tr>
					))}
				</tbody>
			</table>
		</div>
	)
}

export default function PaperTrading() {
	const api = useMemo(() => (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, ''), [])
	const [summary, setSummary] = useState(null)
	const [trades, setTrades] = useState([])
	const [equity, setEquity] = useState([])
	const [config, setConfig] = useState(null)
	const [results, setResults] = useState([])
	const [selected, setSelected] = useState('')
	const [result, setResult] = useState(null)
	const [loading, setLoading] = useState(true)
	const [error, setError] = useState('')

	useEffect(() => {
		let cancelled = false
		const get = (path) => fetch(`${api}/api/paper/${path}`).then((r) => r.json())
		Promise.all([get('summary'), get('trades'), get('equity'), get('config'), get('backtests')])
			.then(([s, t, e, c, b]) => {
				if (cancelled) return
				if (s.success === false) throw new Error(s.message)
				setSummary(s)
				setTrades((t.trades || []).slice().reverse())
				setEquity(e.equity || [])
				setConfig(c.config || null)
				setResults(b.results || [])
				if (b.results?.length) setSelected(b.results[0].name)
			})
			.catch((err) => !cancelled && setError(err.message || 'Could not load the paper record'))
			.finally(() => !cancelled && setLoading(false))
		return () => { cancelled = true }
	}, [api])

	useEffect(() => {
		if (!selected) return
		let cancelled = false
		setResult(null)
		fetch(`${api}/api/paper/backtests/${encodeURIComponent(selected)}`)
			.then((r) => r.json())
			.then((j) => !cancelled && setResult(j.success === false ? null : j))
			.catch(() => !cancelled && setResult(null))
		return () => { cancelled = true }
	}, [api, selected])

	if (loading) {
		return <div className="content"><Empty>Loading the paper record…</Empty></div>
	}
	if (error) {
		return (
			<div className="content" style={{ maxWidth: 1200, margin: '0 auto', width: '100%' }}>
				<h1>Paper Trading</h1>
				<div className="message error">{error}</div>
			</div>
		)
	}

	const cap = summary.capital
	const pnl = summary.value - cap
	const missed = (summary.notes || []).filter((n) => n.note.startsWith('not simulated')).length

	return (
		<div className="content" style={{ maxWidth: 1200, margin: '0 auto', width: '100%' }}>
			<div style={{ marginBottom: 'var(--space-6)' }}>
				<h1 style={{ marginBottom: 'var(--space-2)' }}>Paper Trading</h1>
				<p style={{ margin: 0 }}>
					Nifty weekly options from the RSI signal, simulated on Breeze history - no orders are placed.
					Up to date through <strong style={{ color: 'var(--text)' }}>{longDay(summary.last_processed)}</strong>,
					since {longDay(summary.start)}.
				</p>
			</div>

			<div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 'var(--space-3)', marginBottom: 'var(--space-6)' }}>
				<Stat label="Account value" value={inr(summary.value)} sub={`${inr(pnl)} on ${inr(cap)}`} color={tone(pnl)} />
				<Stat label="Return" value={pct(summary.return_pct)} sub={`Nifty ${pct(summary.benchmark_return_pct)}`} color={tone(summary.return_pct)} />
				<Stat label="Trades" value={summary.trades} sub={summary.trades ? `${summary.winning_trades} won · ${summary.by_exit.stop} stopped out` : 'No signal yet'} />
				<Stat label="Max drawdown" value={pct(summary.max_drawdown_pct)} sub={`${summary.sessions} sessions`} />
				<Stat label="Charges paid" value={inr(summary.charges_paid)} sub="Brokerage, STT, fees" />
			</div>

			<Section title="Account vs Nifty" aside={missed > 0 && <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>{missed} recent sessions skipped - no Breeze login that day</span>}>
				{equity.length > 1 ? (
					<div style={{ width: '100%', height: 280 }}>
						<ResponsiveContainer>
							<LineChart data={equity} margin={{ left: 8, right: 16, top: 8, bottom: 0 }}>
								<CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
								<XAxis dataKey="date" tickFormatter={day} stroke="var(--text-muted)" fontSize={12} minTickGap={24} />
								<YAxis domain={['auto', 'auto']} tickFormatter={(v) => inr(v)} stroke="var(--text-muted)" fontSize={12} width={88} />
								<Tooltip
									contentStyle={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 6 }}
									labelFormatter={longDay}
									formatter={(v, name) => [inr(v), name]}
								/>
								<Legend wrapperStyle={{ fontSize: 13 }} />
								<Line type="monotone" dataKey="value" name="Paper account" stroke="var(--accent)" dot={false} strokeWidth={2} />
								<Line type="monotone" dataKey="benchmark" name="Nifty (same capital)" stroke="var(--text-muted)" dot={false} strokeWidth={1.5} strokeDasharray="4 3" />
							</LineChart>
						</ResponsiveContainer>
					</div>
				) : (
					<Empty>The chart starts after the second session.</Empty>
				)}
			</Section>

			<Section title="Trades">
				{trades.length ? (
					<div style={{ overflowX: 'auto' }}>
						<table className="table" style={{ minWidth: 820, fontVariantNumeric: 'tabular-nums' }}>
							<thead>
								<tr>
									<th>Date</th><th>Contract</th><th>Signal</th><th>Entry</th><th>Exit</th><th>Exit reason</th><th>Held</th><th style={{ textAlign: 'right' }}>P&L</th>
								</tr>
							</thead>
							<tbody>
								{trades.map((t) => (
									<tr key={t.id}>
										<td>{day(t.date)}</td>
										<td>{t.label}</td>
										<td style={{ color: 'var(--text-secondary)' }}>{t.rsi != null ? `RSI ${num(t.rsi, 1)}` : t.setup || '–'}</td>
										<td>{inr(t.entry_price, 2)} <span style={{ color: 'var(--text-muted)' }}>{hhmm(t.entry_time)}</span></td>
										<td>{inr(t.exit_price, 2)} <span style={{ color: 'var(--text-muted)' }}>{hhmm(t.exit_time)}</span></td>
										<td>{EXIT_LABEL[t.exit_reason] || t.exit_reason}</td>
										<td>{t.held_minutes} min</td>
										<td style={{ textAlign: 'right', color: tone(t.pnl) }}>
											{inr(t.pnl)} <span style={{ fontSize: 12 }}>({pct(t.pnl_pct)})</span>
										</td>
									</tr>
								))}
							</tbody>
						</table>
					</div>
				) : (
					<Empty>No trades yet - the strategy only trades when RSI crosses its thresholds.</Empty>
				)}
			</Section>

			<Section
				title="Backtests"
				aside={results.length > 0 && (
					<select value={selected} onChange={(e) => setSelected(e.target.value)} style={{ width: 'auto', maxWidth: '100%' }} aria-label="Saved backtest">
						{results.map((r) => (
							<option key={r.name} value={r.name}>{r.name}{r.kind === 'sweep' ? ' (sweep)' : ''}</option>
						))}
					</select>
				)}
			>
				{!results.length && <Empty>No saved backtests. Run one with python -m backend.paper.backtest.</Empty>}
				{results.length > 0 && !result && <Empty>Loading…</Empty>}
				{result && (
					<>
						<div style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 'var(--space-3)' }}>
							{longDay(result.start)} – {longDay(result.end)}
							{result.split ? ` · out-of-sample from ${longDay(result.split)}` : ''}
							{result.config?.sides && result.config.sides !== 'both' ? ` · ${result.config.sides}s only` : ''}
						</div>
						<BacktestReport result={result} />
					</>
				)}
			</Section>

			{config && (
				<Section title="Strategy settings" aside={<span style={{ color: 'var(--text-muted)', fontSize: 13 }}>Applies from the next session</span>}>
					<div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 'var(--space-4)' }}>
						{[
							['Signal', config.strategy === 'rsi' || !config.strategy
								? `RSI(${config.rsi_period}) < ${config.oversold} → call, > ${config.overbought} → put`
								: config.strategy],
							['Sides traded', config.sides ? { both: 'Calls and puts', call: 'Calls only', put: 'Puts only' }[config.sides] : 'Calls and puts'],
							['Exit', `+${config.target_pct}% target, −${config.stop_pct}% stop, square-off ${config.square_off}`],
							['Entry window', `${config.first_entry} – ${config.last_entry}, ${config.max_trades_per_day} trade a day`],
							['Size', `${config.lots} lot × ${config.lot_size} (ATM weekly)`],
							['Capital', inr(config.capital)],
						].map(([label, value]) => (
							<div key={label}>
								<div style={{ color: 'var(--text-muted)', fontSize: 12, fontWeight: 500, textTransform: 'uppercase', letterSpacing: 0.5 }}>{label}</div>
								<div style={{ marginTop: 4 }}>{value}</div>
							</div>
						))}
					</div>
				</Section>
			)}
		</div>
	)
}
