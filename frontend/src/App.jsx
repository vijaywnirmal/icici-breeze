import React, { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

export default function App() {
	const [apiKey, setApiKey] = useState('')
	const [apiSecret, setApiSecret] = useState('')
	const [sessionKey, setSessionKey] = useState('')
	const [loading, setLoading] = useState(false)
	const [message, setMessage] = useState('')
	const [status, setStatus] = useState('idle') // 'idle' | 'success' | 'error'
	const navigate = useNavigate()

	const apiBase = import.meta.env.VITE_API_BASE_URL || ''
	const loginUrl = useMemo(() => {
		const base = (apiBase || '').replace(/\/$/, '')
		return `${base}/api/login`
	}, [apiBase])

	async function onSubmit(e) {
		e.preventDefault()
		setStatus('idle')
		setMessage('')
		
		// Validate all fields are provided
		if (!apiKey.trim() || !apiSecret.trim() || !sessionKey.trim()) {
			setStatus('error')
			setMessage('All fields are required: API Key, API Secret, and Session Key')
			return
		}
		
		setLoading(true)
		try {
			const res = await fetch(loginUrl, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ 
					api_key: apiKey.trim(),
					api_secret: apiSecret.trim(),
					session_key: sessionKey.trim()
				})
			})
			const data = await res.json().catch(() => ({}))
			if (!res.ok || data.success === false) {
				const errText = data?.message || data?.error || 'Login failed'
				setStatus('error')
				setMessage(errText)
				return
			}
			// store session key for later profile fetch
			if (sessionKey.trim()) {
				try { sessionStorage.setItem('api_session', sessionKey.trim()) } catch {}
			}
			setStatus('success')
			setMessage('Login successful.')
			navigate('/home', { replace: true })
		} catch (err) {
			setStatus('error')
			setMessage(err?.message || 'Something went wrong')
		} finally {
			setLoading(false)
		}
	}

	return (
		<main className="container">
			<section className="card">
				<div style={{ textAlign: 'center', marginBottom: 'var(--space-8)' }}>
					<h1 style={{ color: 'var(--text)', fontFamily: 'var(--font-sans)', marginBottom: 'var(--space-2)' }}>
						Breeze Trading
					</h1>
					<p style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-sans)' }}>
						Sign in to continue
					</p>
				</div>
				
				<form onSubmit={onSubmit}>
					<div>
						<label htmlFor="apiKey">API Key</label>
						<input 
							id="apiKey" 
							type="text" 
							placeholder="Enter API Key" 
							value={apiKey} 
							onChange={(e) => setApiKey(e.target.value)}
							required 
						/>
					</div>

					<div>
						<label htmlFor="apiSecret">API Secret</label>
						<input 
							id="apiSecret" 
							type="password" 
							placeholder="Enter API Secret" 
							value={apiSecret} 
							onChange={(e) => setApiSecret(e.target.value)}
							required 
						/>
					</div>

					<div>
						<label htmlFor="sessionKey">Session Key</label>
						<input 
							id="sessionKey" 
							type="password" 
							placeholder="Enter Session Key" 
							value={sessionKey} 
							onChange={(e) => setSessionKey(e.target.value)}
							required 
						/>
					</div>

					<button type="submit" disabled={loading}>
						{loading && <span className="spinner" aria-hidden="true"></span>}
						<span>{loading ? 'Signing in...' : 'Sign in'}</span>
					</button>
				</form>
				
				{message && (
					<div 
						style={{
							padding: 'var(--space-3)',
							borderRadius: 'var(--radius)',
							marginTop: 'var(--space-4)',
							border: '1px solid',
							borderColor: status === 'error' ? 'var(--danger)' : status === 'success' ? 'var(--success)' : 'var(--border)',
							backgroundColor: 'var(--panel)',
							color: status === 'error' ? 'var(--danger)' : status === 'success' ? 'var(--success)' : 'var(--text)',
							fontFamily: 'var(--font-sans)',
							fontSize: '14px'
						}}
						role="status" 
						aria-live="polite"
					>
						{message}
					</div>
				)}
			</section>
		</main>
	)
}
