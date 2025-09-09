import React, { useMemo } from 'react'
import { create } from 'zustand'
import { Card, CardHeader, CardContent } from '../components/ui/Card'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import Select from '../components/ui/Select'
import Label from '../components/ui/Label'
import Typography from '../components/ui/Typography'

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
		<div className="content" style={{
			display: 'grid',
			gridTemplateColumns: '1fr 420px',
			gap: 'var(--space-6)',
			width: '100%',
			maxWidth: '1200px',
			margin: '0 auto'
		}}>
			{/* Main Strategy Builder */}
			<Card variant="elevated">
				<CardHeader>
					<Typography variant="h1">Strategy Builder</Typography>
				</CardHeader>
				<CardContent>
					{/* Strategy Meta Information */}
					<div style={{
						display: 'grid',
						gridTemplateColumns: 'repeat(3, 1fr)',
						gap: 'var(--space-4)',
						marginBottom: 'var(--space-8)'
					}}>
						<div>
							<Label required>Strategy Name</Label>
							<Input 
								value={name} 
								onChange={(e) => setMeta({ name: e.target.value })}
								placeholder="Enter strategy name"
							/>
						</div>
						<div>
							<Label>Description</Label>
							<Input 
								value={description} 
								onChange={(e) => setMeta({ description: e.target.value })}
								placeholder="Enter description"
							/>
						</div>
						<div>
							<Label>Universe</Label>
							<Select 
								multiple 
								value={universe} 
								onChange={(e) => setMeta({ universe: Array.from(e.target.selectedOptions).map(o => o.value) })}
							>
								{symbols.map(s => <option key={s} value={s}>{s}</option>)}
							</Select>
						</div>
					</div>

					{/* Conditions Section */}
					<div style={{ marginBottom: 'var(--space-8)' }}>
						<div style={{
							display: 'flex',
							alignItems: 'center',
							justifyContent: 'space-between',
							marginBottom: 'var(--space-4)'
						}}>
							<Typography variant="h3">Conditions</Typography>
							<div style={{ display: 'flex', gap: 'var(--space-2)' }}>
								<Select 
									onChange={(e) => e.target.value && loadTemplate(e.target.value)} 
									defaultValue=""
									style={{ width: '200px' }}
								>
									<option value="" disabled>Choose a template…</option>
									<option value="Moving Average Crossover">Moving Average Crossover</option>
									<option value="RSI Overbought/Oversold">RSI Overbought/Oversold</option>
									<option value="Breakout">Breakout</option>
								</Select>
							</div>
						</div>
						
						{conditions.map((c, idx) => (
							<Card key={idx} variant="default" style={{ marginBottom: 'var(--space-3)' }}>
								<CardContent>
									<div style={{
										display: 'grid',
										gridTemplateColumns: 'repeat(5, 1fr) auto',
										gap: 'var(--space-3)',
										alignItems: 'end'
									}}>
										<div>
											<Label>Indicator</Label>
											<Select value={c.indicator} onChange={(e) => updateCondition(idx, { indicator: e.target.value })}>
												{indicators.map(x => <option key={x} value={x}>{x}</option>)}
											</Select>
										</div>
										<div>
											<Label>Symbol</Label>
											<Select value={c.symbol} onChange={(e) => updateCondition(idx, { symbol: e.target.value })}>
												{symbols.map(x => <option key={x} value={x}>{x}</option>)}
											</Select>
										</div>
										<div>
											<Label>Timeframe</Label>
											<Select value={c.timeframe} onChange={(e) => updateCondition(idx, { timeframe: e.target.value })}>
												{timeframes.map(x => <option key={x} value={x}>{x}</option>)}
											</Select>
										</div>
										<div>
											<Label>Operator</Label>
											<Select value={c.operator} onChange={(e) => updateCondition(idx, { operator: e.target.value })}>
												{operators.map(x => <option key={x} value={x}>{x}</option>)}
											</Select>
										</div>
										<div>
											<Label>Value</Label>
											<Input 
												value={String(c.value)} 
												onChange={(e) => updateCondition(idx, { value: e.target.value })}
												placeholder="Threshold"
											/>
										</div>
										<Button 
											variant="danger" 
											size="sm" 
											onClick={() => removeCondition(idx)}
											style={{ height: 'var(--size-md)' }}
										>
											Remove
										</Button>
									</div>
								</CardContent>
							</Card>
						))}
						
						<Button variant="outline" onClick={addCondition} style={{ width: 'auto' }}>
							+ Add Condition
						</Button>
					</div>

					{/* Actions Section */}
					<div style={{ marginBottom: 'var(--space-8)' }}>
						<Typography variant="h3" style={{ marginBottom: 'var(--space-4)' }}>Actions</Typography>
						
						{actions.map((a, idx) => (
							<Card key={idx} variant="default" style={{ marginBottom: 'var(--space-3)' }}>
								<CardContent>
									<div style={{
										display: 'grid',
										gridTemplateColumns: 'repeat(4, 1fr) auto',
										gap: 'var(--space-3)',
										alignItems: 'end'
									}}>
										<div>
											<Label>Signal</Label>
											<Select value={a.signal} onChange={(e) => updateAction(idx, { signal: e.target.value as any })}>
												{signals.map(x => <option key={x} value={x}>{x}</option>)}
											</Select>
										</div>
										<div>
											<Label>Instrument</Label>
											<Select value={a.instrument} onChange={(e) => updateAction(idx, { instrument: e.target.value })}>
												{instruments.map(x => <option key={x} value={x}>{x}</option>)}
											</Select>
										</div>
										<div>
											<Label>Expiry</Label>
											<Select value={a.expiry} onChange={(e) => updateAction(idx, { expiry: e.target.value as any })}>
												{expiries.map(x => <option key={x} value={x}>{x}</option>)}
											</Select>
										</div>
										<div>
											<Label>Strike</Label>
											<Select value={a.strike} onChange={(e) => updateAction(idx, { strike: e.target.value })}>
												{strikes.map(x => <option key={x} value={x}>{x}</option>)}
											</Select>
										</div>
										<Button 
											variant="danger" 
											size="sm" 
											onClick={() => removeAction(idx)}
											style={{ height: 'var(--size-md)' }}
										>
											Remove
										</Button>
									</div>
								</CardContent>
							</Card>
						))}
						
						<Button variant="outline" onClick={addAction} style={{ width: 'auto' }}>
							+ Add Action
						</Button>
					</div>

					{/* Save Button */}
					<div style={{ display: 'flex', justifyContent: 'flex-end' }}>
						<Button variant="primary" onClick={onSave} size="lg">
							💾 Save Strategy
						</Button>
					</div>
				</CardContent>
			</Card>

			{/* JSON Preview Sidebar */}
			<Card variant="elevated">
				<CardHeader>
					<Typography variant="h3">Preview JSON</Typography>
				</CardHeader>
				<CardContent>
					<pre style={{
						whiteSpace: 'pre-wrap',
						background: 'var(--panel-hover)',
						padding: 'var(--space-4)',
						borderRadius: 'var(--radius)',
						fontSize: '12px',
						fontFamily: 'var(--font-mono)',
						color: 'var(--text)',
						border: '1px solid var(--border)',
						overflow: 'auto',
						maxHeight: '500px'
					}}>
						{pretty}
					</pre>
				</CardContent>
			</Card>
		</div>
	)
}


