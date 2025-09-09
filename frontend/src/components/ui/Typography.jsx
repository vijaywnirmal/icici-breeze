import React from 'react'

export default function Typography({ 
	className = '', 
	children, 
	variant = 'body1',
	color = 'default',
	...props 
}) {
	const getVariantStyles = () => {
		switch (variant) {
			case 'h1':
				return {
					fontSize: '32px',
					fontWeight: 700,
					lineHeight: 1.2,
					marginBottom: 'var(--space-6)'
				}
			case 'h2':
				return {
					fontSize: '24px',
					fontWeight: 600,
					lineHeight: 1.3,
					marginBottom: 'var(--space-4)'
				}
			case 'h3':
				return {
					fontSize: '20px',
					fontWeight: 600,
					lineHeight: 1.3,
					marginBottom: 'var(--space-4)'
				}
			case 'h4':
				return {
					fontSize: '18px',
					fontWeight: 600,
					lineHeight: 1.3,
					marginBottom: 'var(--space-3)'
				}
			case 'h5':
				return {
					fontSize: '16px',
					fontWeight: 600,
					lineHeight: 1.3,
					marginBottom: 'var(--space-3)'
				}
			case 'h6':
				return {
					fontSize: '14px',
					fontWeight: 600,
					lineHeight: 1.3,
					marginBottom: 'var(--space-2)'
				}
			case 'body1':
				return {
					fontSize: '16px',
					fontWeight: 400,
					lineHeight: 1.5,
					marginBottom: 'var(--space-4)'
				}
			case 'body2':
				return {
					fontSize: '14px',
					fontWeight: 400,
					lineHeight: 1.5,
					marginBottom: 'var(--space-3)'
				}
			case 'caption':
				return {
					fontSize: '12px',
					fontWeight: 400,
					lineHeight: 1.4,
					marginBottom: 'var(--space-2)'
				}
			case 'overline':
				return {
					fontSize: '12px',
					fontWeight: 600,
					lineHeight: 1.4,
					textTransform: 'uppercase',
					letterSpacing: '0.5px',
					marginBottom: 'var(--space-2)'
				}
			default:
				return {
					fontSize: '14px',
					fontWeight: 400,
					lineHeight: 1.5,
					marginBottom: 'var(--space-3)'
				}
		}
	}

	const getColorStyles = () => {
		switch (color) {
			case 'primary':
				return { color: 'var(--text)' }
			case 'secondary':
				return { color: 'var(--text-secondary)' }
			case 'muted':
				return { color: 'var(--text-muted)' }
			case 'success':
				return { color: 'var(--success)' }
			case 'danger':
				return { color: 'var(--danger)' }
			case 'warning':
				return { color: 'var(--warning)' }
			case 'accent':
				return { color: 'var(--accent)' }
			default:
				return { color: 'var(--text)' }
		}
	}

	const Component = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'].includes(variant) ? variant : 'div'

	return (
		<Component
			className={className}
			style={{
				fontFamily: 'var(--font-sans)',
				margin: 0,
				...getVariantStyles(),
				...getColorStyles(),
				...props.style
			}}
			{...props}
		>
			{children}
		</Component>
	)
}
