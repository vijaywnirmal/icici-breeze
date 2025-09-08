import React, { useEffect, useState, useMemo, useRef } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Dropdown, DropdownItem } from './ui/Dropdown.jsx'
import Button from './ui/Button.jsx'

export default function CustomerProfile({ layout = 'sidebar' }) {
	const [customerData, setCustomerData] = useState(null)
	const [loading, setLoading] = useState(true)
	const [showDropdown, setShowDropdown] = useState(false)
	const navigate = useNavigate()
	const dropdownRef = useRef(null)
	
	const apiBase = import.meta.env.VITE_API_BASE_URL || ''
	const api = useMemo(() => (apiBase || '').replace(/\/$/, ''), [apiBase])

	function makeUrl(path) {
		try {
			const base = api || window.location.origin
			return new URL(path, base).toString()
		} catch {
			return path
		}
	}

	useEffect(() => {
		let cancelled = false
		async function fetchProfile() {
			setLoading(true)
			try {
				const sess = sessionStorage.getItem('api_session') || ''
				// Prefer the dedicated account details endpoint
				let detailsUrl = makeUrl('/api/account/details')
				if (sess) {
					const u = new URL(detailsUrl)
					u.searchParams.set('api_session', sess)
					detailsUrl = u.toString()
				}
				let res = await fetch(detailsUrl)
				let data = await res.json().catch(() => ({}))
				if (!data?.success || !data?.customer) {
					// Fallback to /profile if needed
					let profileUrl = makeUrl('/api/profile')
					if (sess) {
						const u2 = new URL(profileUrl)
						u2.searchParams.set('api_session', sess)
						profileUrl = u2.toString()
					}
					res = await fetch(profileUrl)
					data = await res.json().catch(() => ({}))
				}
				if (!cancelled && data?.success) {
					const payload = data.customer || data.profile || null
					const profileData = payload?.Success || payload
					if (profileData) setCustomerData(profileData)
				}
			} catch (error) {
				console.error('Failed to fetch customer profile:', error)
			} finally {
				if (!cancelled) setLoading(false)
			}
		}
		
		fetchProfile()
		return () => { cancelled = true }
	}, [api])

	// Handle click outside to close dropdown
	useEffect(() => {
		function handleClickOutside(event) {
			if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
				setShowDropdown(false)
			}
		}

		if (showDropdown) {
			document.addEventListener('mousedown', handleClickOutside)
			return () => document.removeEventListener('mousedown', handleClickOutside)
		}
	}, [showDropdown])

	const handleLogout = () => {
		sessionStorage.removeItem('api_session')
		navigate('/', { replace: true })
	}

	// Extract display name from customer data
	const getDisplayName = () => {
		if (!customerData) return 'User'
		
		// Extract first name from idirect_user_name or user_name
		const fullName = customerData.idirect_user_name || customerData.user_name || ''
		const first = String(fullName).trim().split(/\s+/)[0] || ''
		if (first) return first
		
		// Fallback to email or user ID
		return customerData.email_id || customerData.user_id || 'User'
	}

	const getUserInitials = () => {
		const name = getDisplayName()
		const parts = name.split(' ').filter(p => p.length > 0)
		if (parts.length >= 2) {
			return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
		}
		return name.substring(0, 2).toUpperCase()
	}

	if (loading) {
		return (
			<div className={layout === 'sidebar' ? 'sidebar-profile loading' : 'customer-profile'}>
				<div className="profile-spinner"></div>
			</div>
		)
	}

	if (layout === 'sidebar') {
		return (
			<div className="sidebar-profile" ref={dropdownRef}>
				<Dropdown
					trigger={<div className="sidebar-profile-item"><svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M12 12c2.761 0 5-2.239 5-5s-2.239-5-5-5-5 2.239-5 5 2.239 5 5 5zm0 2c-4.418 0-8 2.239-8 5v1h16v-1c0-2.761-3.582-5-8-5z" stroke="currentColor" strokeWidth="1"/></svg><span>Profile</span></div>}
				>
					{() => (
						<div className="profile-info">
							{customerData && (
								<>
									<div className="info-item"><span className="info-label">User ID:</span><span className="info-value">{customerData.idirect_userid || customerData.user_id || 'N/A'}</span></div>
									<div className="info-item"><span className="info-label">Name:</span><span className="info-value">{getDisplayName()}</span></div>
								</>
							)}
							<Link to="/holidays" className="sidebar-profile-item">
								<svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M3 5h18M8 5v14m8-14v14M3 19h18" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
								<span>Holidays</span>
							</Link>
							<DropdownItem onClick={handleLogout}>Logout</DropdownItem>
						</div>
					)}
				</Dropdown>
			</div>
		)
	}

	return null
}
