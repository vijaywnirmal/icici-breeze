import React, { useMemo } from 'react'
import { create } from 'zustand'

type Condition = {
	indicator: string
	symbol: string
	timeframe: string
	operator: string
	value: string | number
}

type Action = {
	type: 'signal' | 'trade'
	signal: 'BUY' | 'SELL'
	instrument: string
	strike: string
	expiry: 'weekly' | 'monthly'
}

type StrategyState = {
	name: string
	description: string
	universe: string[]
	conditions: Condition[]
	actions: Action[]
	addCondition: () => void
	updateCondition: (idx: number, patch: Partial<Condition>) => void
	removeCondition: (idx: number) => void
	addAction: () => void
	updateAction: (idx: number, patch: Partial<Action>) => void
	removeAction: (idx: number) => void
	setMeta: (patch: Partial<Pick<StrategyState, 'name' | 'description' | 'universe'>>) => void
}

const useStrategyStore = create<StrategyState>((set) => ({
	name: 'My Strategy',
	description: '',
	universe: ['NIFTY'],
	conditions: [
		{ indicator: 'RSI', symbol: 'NIFTY', timeframe: '5m', operator: '<', value: 20 }
	],
	actions: [
		{ type: 'trade', signal: 'BUY', instrument: 'OPTION', strike: 'ATM', expiry: 'weekly' }
	],
	addCondition: () => set((s) => ({ conditions: [...s.conditions, { indicator: 'RSI', symbol: 'NIFTY', timeframe: '5m', operator: '<', value: 20 }] })),
	updateCondition: (idx, patch) => set((s) => ({ conditions: s.conditions.map((c, i) => i === idx ? { ...c, ...patch } : c) })),
	removeCondition: (idx) => set((s) => ({ conditions: s.conditions.filter((_, i) => i !== idx) })),
	addAction: () => set((s) => ({ actions: [...s.actions, { type: 'trade', signal: 'BUY', instrument: 'OPTION', strike: 'ATM', expiry: 'weekly' }] })),
	updateAction: (idx, patch) => set((s) => ({ actions: s.actions.map((a, i) => i === idx ? { ...a, ...patch } : a) })),
	removeAction: (idx) => set((s) => ({ actions: s.actions.filter((_, i) => i !== idx) })),
	setMeta: (patch) => set((s) => ({ ...s, ...patch })),
}))

const indicators = ['RSI', 'SMA', 'EMA']
const symbols = ['NIFTY', 'BANKNIFTY', 'NIFTY_OPTIONS']
const timeframes = ['1m','5m','15m','1h','1d']
const operators = ['<','>','crosses_above','crosses_below']
const signals = ['BUY','SELL'] as const
const instruments = ['OPTION','FUTURES']
const expiries = ['weekly','monthly'] as const
const strikes = ['ATM','OTM+1','OTM+2','ITM-1','ITM-2']

export default function StrategyBuilder() {
	const {
		name, description, universe, conditions, actions,
		addCondition, updateCondition, removeCondition,
		addAction, updateAction, removeAction,
		setMeta
	} = useStrategyStore()

	const apiBase = (import.meta as any).env?.VITE_API_BASE_URL || ''
	const api = useMemo(() => (apiBase || '').replace(/\/$/, ''), [apiBase])

	const strategyJson = useMemo(() => ({ name, description, universe, conditions, actions }), [name, description, universe, conditions, actions])
	const pretty = useMemo(() => JSON.stringify(strategyJson, null, 2), [strategyJson])

	async function loadTemplate(name: string) {
		const res = await fetch(`${api}/api/strategies/templates`)
		const j = await res.json().catch(() => ({}))
		const items = Array.isArray(j?.items) ? j.items : []
		const found = items.find((it: any) => (it?.name || '').toLowerCase().includes(name.toLowerCase()))
		if (found) {
			setMeta({ name: found.name, description: found.description, universe: found.universe || [] })
			// @ts-ignore
			useStrategyStore.setState({ conditions: found.conditions || [], actions: found.actions || [] })
		}
	}

	async function onSave() {
		const payload = { name, description, json: strategyJson }
		const res = await fetch(`${api}/api/strategies/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
		const j = await res.json().catch(() => ({}))
		alert(j?.success ? `Saved: ${j.id}` : (j?.message || 'Failed'))
	}

	return (
		<div className="content card" style={{display:'grid', gridTemplateColumns:'1fr 420px', gap:16, width:'100%', maxWidth:1200}}>
			<div>
				<h1>Strategy Builder</h1>
				<div className="grid" style={{gridTemplateColumns:'repeat(3, minmax(160px, 1fr))', gap:12}}>
					<div>
						<label>Name</label>
						<input value={name} onChange={(e) => setMeta({ name: e.target.value })} />
					</div>
					<div>
						<label>Description</label>
						<input value={description} onChange={(e) => setMeta({ description: e.target.value })} />
					</div>
					<div>
						<label>Universe</label>
						<select multiple value={universe} onChange={(e) => setMeta({ universe: Array.from(e.target.selectedOptions).map(o => o.value) })}>
							{symbols.map(s => <option key={s} value={s}>{s}</option>)}
						</select>
					</div>
				</div>

				<h3 style={{marginTop:16, display:'flex', alignItems:'center', justifyContent:'space-between'}}>
					<span>Conditions</span>
					<span style={{display:'inline-flex', gap:8}}>
						<select onChange={(e) => e.target.value && loadTemplate(e.target.value)} defaultValue="">
							<option value="" disabled>Choose a template…</option>
							<option value="Moving Average Crossover">Moving Average Crossover</option>
							<option value="RSI Overbought/Oversold">RSI Overbought/Oversold</option>
							<option value="Breakout">Breakout</option>
						</select>
					</span>
				</h3>
				{conditions.map((c, idx) => (
					<div key={idx} className="grid" style={{gridTemplateColumns:'repeat(5, minmax(120px, 1fr)) auto', gap:8, margin:'8px 0'}}>
						<select value={c.indicator} onChange={(e) => updateCondition(idx, { indicator: e.target.value })}>
							{indicators.map(x => <option key={x} value={x}>{x}</option>)}
						</select>
						<select value={c.symbol} onChange={(e) => updateCondition(idx, { symbol: e.target.value })}>
							{symbols.map(x => <option key={x} value={x}>{x}</option>)}
						</select>
						<select value={c.timeframe} onChange={(e) => updateCondition(idx, { timeframe: e.target.value })}>
							{timeframes.map(x => <option key={x} value={x}>{x}</option>)}
						</select>
						<select value={c.operator} onChange={(e) => updateCondition(idx, { operator: e.target.value })}>
							{operators.map(x => <option key={x} value={x}>{x}</option>)}
						</select>
						<input value={String(c.value)} onChange={(e) => updateCondition(idx, { value: e.target.value })} />
						<button onClick={() => removeCondition(idx)}>Remove</button>
					</div>
				))}
				<button onClick={addCondition}>Add Condition</button>

				<h3 style={{marginTop:16}}>Actions</h3>
				{actions.map((a, idx) => (
					<div key={idx} className="grid" style={{gridTemplateColumns:'repeat(5, minmax(120px, 1fr)) auto', gap:8, margin:'8px 0'}}>
						<select value={a.signal} onChange={(e) => updateAction(idx, { signal: e.target.value as any })}>
							{signals.map(x => <option key={x} value={x}>{x}</option>)}
						</select>
						<select value={a.instrument} onChange={(e) => updateAction(idx, { instrument: e.target.value })}>
							{instruments.map(x => <option key={x} value={x}>{x}</option>)}
						</select>
						<select value={a.expiry} onChange={(e) => updateAction(idx, { expiry: e.target.value as any })}>
							{expiries.map(x => <option key={x} value={x}>{x}</option>)}
						</select>
						<select value={a.strike} onChange={(e) => updateAction(idx, { strike: e.target.value })}>
							{strikes.map(x => <option key={x} value={x}>{x}</option>)}
						</select>
						<button onClick={() => removeAction(idx)}>Remove</button>
					</div>
				))}
				<button onClick={addAction}>Add Action</button>

				<div style={{marginTop:16}}>
					<button onClick={onSave}>Save Strategy</button>
				</div>
			</div>

			<aside>
				<h3>Preview JSON</h3>
				<pre style={{whiteSpace:'pre-wrap', background:'#0f141d', padding:12, borderRadius:8, fontSize:12}}>{pretty}</pre>
			</aside>
		</div>
	)
}


