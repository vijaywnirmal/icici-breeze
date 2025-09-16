import React, { useState, useMemo } from 'react'

export default function LoginPage() {
	const [apiKey, setApiKey] = useState('')
	const [apiSecret, setApiSecret] = useState('')
	const [sessionKey, setSessionKey] = useState('')
	const [loading, setLoading] = useState(false)
	const [error, setError] = useState('')

	const apiBase = useMemo(() => {
		if (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_BASE_URL) {
			return String(process.env.NEXT_PUBLIC_API_BASE_URL).replace(/\/$/, '')
		}
		if (typeof window !== 'undefined') {
			return window.location.origin
		}
		return ''
	}, [])

	async function onSubmit(e) {
		e.preventDefault()
		setError('')
		setLoading(true)
		try {
			const res = await fetch(`${apiBase}/api/login`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ api_key: apiKey, api_secret: apiSecret, session_key: sessionKey })
			})
			const json = await res.json().catch(() => ({}))
			if (!res.ok || json?.success === false) {
				throw new Error(json?.message || json?.error || 'Login failed')
			}
			try { sessionStorage.setItem('api_session', sessionKey) } catch {}
			window.location.replace('/')
		} catch (err) {
			setError(err?.message || 'Something went wrong')
		} finally {
			setLoading(false)
		}
	}

	return (
		<div className="login-container">
			<div className="login-background">
				<div className="gradient-orb gradient-orb-1" />
				<div className="gradient-orb gradient-orb-2" />
				<div className="gradient-orb gradient-orb-3" />
				<div className="grid-pattern" />
			</div>
			<div className="login-main">
				<div className="login-card">
					<div className="login-header">
						<div className="logo-container">
							<div className="logo-icon">
								<svg width="28" height="28" viewBox="0 0 24 24" fill="none">
									<path d="M12 2L2 7l10 5 10-5-10-5z" stroke="currentColor" strokeWidth="1.5"/>
								</svg>
							</div>
							<div className="logo-text">
								<h1>Breeze Login</h1>
								<p>Enter your Breeze credentials</p>
							</div>
						</div>
					</div>
					<form className="login-form" onSubmit={onSubmit}>
						<div className="form-group">
							<label className="form-label">API Key</label>
							<input className="form-input" type="text" value={apiKey} onChange={(e) => setApiKey(e.target.value)} required />
						</div>
						<div className="form-group">
							<label className="form-label">API Secret</label>
							<input className="form-input" type="password" value={apiSecret} onChange={(e) => setApiSecret(e.target.value)} required />
						</div>
						<div className="form-group">
							<label className="form-label">Session Key</label>
							<input className="form-input" type="password" value={sessionKey} onChange={(e) => setSessionKey(e.target.value)} required />
						</div>
						<button className="login-button" type="submit" disabled={loading}>
							{loading ? <span className="button-spinner" /> : 'Login'}
						</button>
						{error && <div className="message error">{error}</div>}
					</form>
				</div>
			</div>
		</div>
	)
}


