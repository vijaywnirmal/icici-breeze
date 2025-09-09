import React from 'react'

export default function Select({ 
	className = '', 
	variant = 'default', 
	size = 'md', 
	error = false,
	...props 
}) {
	const getSizeStyles = () => {
		switch (size) {
			case 'sm': return { height: 'var(--size-sm)', padding: '0 var(--space-3)', fontSize: '13px' }
			case 'md': return { height: 'var(--size-md)', padding: '0 var(--space-3)', fontSize: '14px' }
			case 'lg': return { height: 'var(--size-lg)', padding: '0 var(--space-4)', fontSize: '14px' }
			default: return { height: 'var(--size-md)', padding: '0 var(--space-3)', fontSize: '14px' }
		}
	}

	const getVariantStyles = () => {
		switch (variant) {
			case 'default':
				return {
					backgroundColor: 'var(--panel)',
					border: `1px solid ${error ? 'var(--danger)' : 'var(--border)'}`,
					color: 'var(--text)'
				}
			case 'outline':
				return {
					backgroundColor: 'transparent',
					border: `1px solid ${error ? 'var(--danger)' : 'var(--border)'}`,
					color: 'var(--text)'
				}
			default:
				return {
					backgroundColor: 'var(--panel)',
					border: `1px solid ${error ? 'var(--danger)' : 'var(--border)'}`,
					color: 'var(--text)'
				}
		}
	}

	return (
		<select
			className={className}
			style={{
				width: '100%',
				borderRadius: 'var(--radius)',
				fontFamily: 'var(--font-sans)',
				outline: 'none',
				transition: 'var(--transition-normal)',
				cursor: 'pointer',
				boxSizing: 'border-box',
				...getSizeStyles(),
				...getVariantStyles(),
				...props.style
			}}
			onFocus={(e) => {
				e.target.style.borderColor = 'var(--accent)'
				e.target.style.boxShadow = '0 0 0 3px rgba(37, 99, 235, 0.1)'
			}}
			onBlur={(e) => {
				e.target.style.borderColor = error ? 'var(--danger)' : 'var(--border)'
				e.target.style.boxShadow = 'none'
			}}
			{...props}
		>
			{props.children}
		</select>
	)
}
