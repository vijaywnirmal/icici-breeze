import React from 'react'

export function Button({ children, as: As = 'button', variant = 'primary', size = 'md', className = '', loading = false, ...props }) {
	const getSizeStyles = () => {
		switch (size) {
			case 'sm': return { height: 'var(--size-sm)', padding: '0 var(--space-3)', fontSize: '13px' }
			case 'md': return { height: 'var(--size-md)', padding: '0 var(--space-4)', fontSize: '14px' }
			case 'lg': return { height: 'var(--size-lg)', padding: '0 var(--space-6)', fontSize: '14px' }
			default: return { height: 'var(--size-md)', padding: '0 var(--space-4)', fontSize: '14px' }
		}
	}

	const getVariantStyles = () => {
		switch (variant) {
			case 'primary':
				return {
					backgroundColor: 'var(--accent)',
					border: '1px solid var(--accent)',
					color: 'white'
				}
			case 'secondary':
				return {
					backgroundColor: 'var(--panel)',
					border: '1px solid var(--border)',
					color: 'var(--text)'
				}
			case 'success':
				return {
					backgroundColor: 'var(--success)',
					border: '1px solid var(--success)',
					color: 'white'
				}
			case 'danger':
				return {
					backgroundColor: 'var(--danger)',
					border: '1px solid var(--danger)',
					color: 'white'
				}
			case 'outline':
				return {
					backgroundColor: 'transparent',
					border: '1px solid var(--border)',
					color: 'var(--text)'
				}
			default:
				return {
					backgroundColor: 'var(--accent)',
					border: '1px solid var(--accent)',
					color: 'white'
				}
		}
	}
	
	return (
		<As 
			className={className}
			style={{
				display: 'inline-flex',
				alignItems: 'center',
				justifyContent: 'center',
				gap: 'var(--space-2)',
				borderRadius: 'var(--radius)',
				fontFamily: 'var(--font-sans)',
				fontWeight: 500,
				cursor: loading || props.disabled ? 'not-allowed' : 'pointer',
				opacity: loading || props.disabled ? 0.5 : 1,
				transition: 'var(--transition-normal)',
				textDecoration: 'none',
				boxSizing: 'border-box',
				position: 'relative',
				overflow: 'hidden',
				outline: 'none',
				...getSizeStyles(),
				...getVariantStyles(),
				...props.style
			}}
			disabled={loading || props.disabled}
			onMouseEnter={(e) => {
				if (!loading && !props.disabled) {
					e.target.style.transform = 'translateY(-1px)'
					e.target.style.boxShadow = 'var(--shadow-md)'
				}
			}}
			onMouseLeave={(e) => {
				if (!loading && !props.disabled) {
					e.target.style.transform = 'translateY(0)'
					e.target.style.boxShadow = 'none'
				}
			}}
			onFocus={(e) => {
				e.target.style.boxShadow = '0 0 0 3px rgba(37, 99, 235, 0.1)'
			}}
			onBlur={(e) => {
				e.target.style.boxShadow = 'none'
			}}
			{...props}
		>
			{loading && (
				<div className="spinner" style={{ width: '14px', height: '14px' }}></div>
			)}
			{children}
		</As>
	)
}

export default Button


