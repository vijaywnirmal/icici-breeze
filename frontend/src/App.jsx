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
		<div className="login-container">
			{/* Background Graphics */}
			<div className="login-background">
				<div className="gradient-orb gradient-orb-1"></div>
				<div className="gradient-orb gradient-orb-2"></div>
				<div className="gradient-orb gradient-orb-3"></div>
				<div className="grid-pattern"></div>
			</div>

			{/* Main Content */}
			<main className="login-main">
				<div className="login-card">
					{/* Header Section */}
					<div className="login-header">
						<div className="logo-container">
							<div className="logo-icon">
								<svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
									<rect width="32" height="32" rx="8" fill="url(#logoGradient)"/>
									<path d="M16 8L10 12l6 4 6-4-6-4z" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
									<path d="M10 20l6 4 6-4" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
									<path d="M10 16l6 4 6-4" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
									<defs>
										<linearGradient id="logoGradient" x1="0%" y1="0%" x2="100%" y2="100%">
											<stop offset="0%" stopColor="#4F46E5"/>
											<stop offset="100%" stopColor="#7C3AED"/>
										</linearGradient>
									</defs>
								</svg>
							</div>
							<div className="logo-text">
								<h1>Breeze Trading</h1>
								<p>Professional Trading Platform</p>
							</div>
						</div>
					</div>

					{/* Form Section */}
					<form className="login-form" onSubmit={onSubmit}>
						<div className="form-group">
							<label htmlFor="apiKey" className="form-label">
								<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
									<rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
									<circle cx="12" cy="16" r="1"/>
									<path d="M7 11V7a5 5 0 0 1 10 0v4"/>
								</svg>
								API Key
							</label>
							<input 
								id="apiKey" 
								type="text" 
								className="form-input"
								placeholder="Enter your API Key" 
								value={apiKey} 
								onChange={(e) => setApiKey(e.target.value)}
								required 
							/>
						</div>

						<div className="form-group">
							<label htmlFor="apiSecret" className="form-label">
								<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
									<rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
									<circle cx="12" cy="16" r="1"/>
									<path d="M7 11V7a5 5 0 0 1 10 0v4"/>
								</svg>
								API Secret
							</label>
							<input 
								id="apiSecret" 
								type="password" 
								className="form-input"
								placeholder="Enter your API Secret" 
								value={apiSecret} 
								onChange={(e) => setApiSecret(e.target.value)}
								required 
							/>
						</div>

						<div className="form-group">
							<label htmlFor="sessionKey" className="form-label">
								<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
									<rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
									<circle cx="12" cy="16" r="1"/>
									<path d="M7 11V7a5 5 0 0 1 10 0v4"/>
								</svg>
								Session Key
							</label>
							<input 
								id="sessionKey" 
								type="password" 
								className="form-input"
								placeholder="Enter your Session Key" 
								value={sessionKey} 
								onChange={(e) => setSessionKey(e.target.value)}
								required 
							/>
						</div>

						<button type="submit" className="login-button" disabled={loading}>
							{loading ? (
								<>
									<div className="button-spinner"></div>
									<span>Signing in...</span>
								</>
							) : (
								<>
									<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
										<path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/>
										<polyline points="10,17 15,12 10,7"/>
										<line x1="15" y1="12" x2="3" y2="12"/>
									</svg>
									<span>Sign in to Platform</span>
								</>
							)}
						</button>
					</form>
					
					{message && (
						<div 
							className={`message ${status}`}
							role="status" 
							aria-live="polite"
						>
							<div className="message-icon">
								{status === 'error' ? (
									<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
										<circle cx="12" cy="12" r="10"/>
										<line x1="15" y1="9" x2="9" y2="15"/>
										<line x1="9" y1="9" x2="15" y2="15"/>
									</svg>
								) : status === 'success' ? (
									<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
										<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
										<polyline points="22,4 12,14.01 9,11.01"/>
									</svg>
								) : (
									<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
										<circle cx="12" cy="12" r="10"/>
										<line x1="12" y1="8" x2="12" y2="12"/>
										<line x1="12" y1="16" x2="12.01" y2="16"/>
									</svg>
								)}
							</div>
							<span>{message}</span>
						</div>
					)}
				</div>
			</main>
		</div>
	)
}
