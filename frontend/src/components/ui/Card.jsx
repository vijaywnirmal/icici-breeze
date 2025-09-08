import React from 'react'

export function Card({ className = '', children, variant = 'default', ...props }) {
	return (
		<div 
			className={className}
			style={{
				backgroundColor: 'var(--panel)',
				border: '1px solid var(--border)',
				borderRadius: 'var(--radius)',
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


