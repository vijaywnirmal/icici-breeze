import React from 'react'

export default function Label({ 
	className = '', 
	children, 
	required = false,
	error = false,
	style,
	...props
}) {
	return (
		<label
			className={className}
			style={{
				display: 'block',
				marginBottom: 'var(--space-2)',
				color: error ? 'var(--danger)' : 'var(--text)',
				fontFamily: 'var(--font-sans)',
				fontSize: '14px',
				fontWeight: 500,
				...style
			}}
			{...props}
		>
			{children}
			{required && (
				<span style={{ color: 'var(--danger)', marginLeft: 'var(--space-1)' }}>*</span>
			)}
		</label>
	)
}
