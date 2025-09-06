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
				<h1>Sign in</h1>
				<form onSubmit={onSubmit}>
					<label htmlFor="apiKey">API Key *</label>
					<input 
						id="apiKey" 
						type="text" 
						placeholder="Enter your Breeze API Key" 
						value={apiKey} 
						onChange={(e) => setApiKey(e.target.value)}
						required 
					/>

					<label htmlFor="apiSecret">API Secret *</label>
					<input 
						id="apiSecret" 
						type="password" 
						placeholder="Enter your Breeze API Secret" 
						value={apiSecret} 
						onChange={(e) => setApiSecret(e.target.value)}
						required 
					/>

					<label htmlFor="sessionKey">Session Key *</label>
					<input 
						id="sessionKey" 
						type="password" 
						placeholder="Enter your Session Key" 
						value={sessionKey} 
						onChange={(e) => setSessionKey(e.target.value)}
						required 
					/>

					<button type="submit" disabled={loading}>
						{loading && <span className="spinner" aria-hidden="true"></span>}
						<span>{loading ? 'Signing in...' : 'Sign in'}</span>
					</button>
				</form>
				<div className={`message ${status === 'error' ? 'error' : status === 'success' ? 'success' : ''}`} role="status" aria-live="polite">
					{message}
				</div>
			</section>
		</main>
	)
}
