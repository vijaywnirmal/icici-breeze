import React from 'react'

export function Card({ className = '', children, variant = 'default', ...props }) {
	const getVariantStyles = () => {
		switch (variant) {
			case 'default':
				return {
					backgroundColor: 'var(--panel)',
					border: '1px solid var(--border)',
					color: 'var(--text)'
				}
			case 'elevated':
				return {
					backgroundColor: 'var(--panel)',
					border: '1px solid var(--border)',
					boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
					color: 'var(--text)'
				}
			case 'success':
				return {
					backgroundColor: 'var(--panel)',
					border: '1px solid var(--success)',
					color: 'var(--text)'
				}
			case 'danger':
				return {
					backgroundColor: 'var(--panel)',
					border: '1px solid var(--danger)',
					color: 'var(--text)'
				}
			case 'warning':
				return {
					backgroundColor: 'var(--panel)',
					border: '1px solid var(--warning)',
					color: 'var(--text)'
				}
			default:
				return {
					backgroundColor: 'var(--panel)',
					border: '1px solid var(--border)',
					color: 'var(--text)'
				}
		}
	}

	return (
		<div 
			className={className}
			style={{
				borderRadius: 'var(--radius)',
				transition: 'all 0.2s ease',
				...getVariantStyles(),
				...props.style
			}}
			{...props}
		>
			{children}
		</div>
	)
}

export function CardHeader({ className = '', children, ...props }) {
	return (
		<div 
			className={className}
			style={{
				padding: 'var(--space-4)',
				borderBottom: '1px solid var(--border)',
				...props.style
			}}
			{...props}
		>
			{children}
		</div>
	)
}

export function CardContent({ className = '', children, ...props }) {
	return (
		<div 
			className={className}
			style={{
				padding: 'var(--space-4)',
				...props.style
			}}
			{...props}
		>
			{children}
		</div>
	)
}

export function CardFooter({ className = '', children, ...props }) {
	return (
		<div 
			className={className}
			style={{
				padding: 'var(--space-4)',
				borderTop: '1px solid var(--border)',
				...props.style
			}}
			{...props}
		>
			{children}
		</div>
	)
}

export default Card


