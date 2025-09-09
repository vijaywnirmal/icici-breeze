import React, { useEffect, useRef, useState } from 'react'

export function Dropdown({ trigger, children, align = 'right', position = 'bottom' }) {
	const [open, setOpen] = useState(false)
	const ref = useRef(null)
	const dropdownRef = useRef(null)

	useEffect(() => {
		function onDoc(e) { 
			if (ref.current && !ref.current.contains(e.target)) setOpen(false) 
		}
		if (open) document.addEventListener('mousedown', onDoc)
		return () => document.removeEventListener('mousedown', onDoc)
	}, [open])

	// Calculate position to prevent going off-screen
	useEffect(() => {
		if (open && dropdownRef.current) {
			const rect = dropdownRef.current.getBoundingClientRect()
			const viewportHeight = window.innerHeight
			const viewportWidth = window.innerWidth
			
			// Check if dropdown goes below viewport
			if (position === 'bottom' && rect.bottom > viewportHeight) {
				dropdownRef.current.style.top = 'auto'
				dropdownRef.current.style.bottom = '100%'
				dropdownRef.current.style.marginBottom = 'var(--space-2)'
				dropdownRef.current.style.marginTop = '0'
			}
			
			// Check if dropdown goes right of viewport
			if (align === 'right' && rect.right > viewportWidth) {
				dropdownRef.current.style.right = '0'
				dropdownRef.current.style.left = 'auto'
			}
		}
	}, [open, align, position])

	return (
		<div 
			ref={ref}
			style={{ position: 'relative' }}
		>
			<div 
				onClick={() => setOpen(v => !v)} 
				style={{ cursor: 'pointer', userSelect: 'none' }}
			>
				{typeof trigger === 'function' ? trigger({ open }) : trigger}
			</div>
			{open && (
				<div 
					ref={dropdownRef}
					style={{
						position: 'absolute',
						top: position === 'bottom' ? '100%' : 'auto',
						bottom: position === 'top' ? '100%' : 'auto',
						left: align === 'left' ? '0' : 'auto',
						right: align === 'right' ? '0' : 'auto',
						marginTop: position === 'bottom' ? 'var(--space-2)' : '0',
						marginBottom: position === 'top' ? 'var(--space-2)' : '0',
						minWidth: '220px',
						backgroundColor: 'var(--panel)',
						border: '1px solid var(--border)',
						borderRadius: 'var(--radius-lg)',
						boxShadow: 'var(--shadow-lg)',
						padding: 'var(--space-2)',
						zIndex: 1000
					}}
				>
					{typeof children === 'function' ? children({ close: () => setOpen(false) }) : children}
				</div>
			)}
		</div>
	)
}

export function DropdownItem({ className = '', children, onClick, ...props }) {
	return (
		<div 
			onClick={onClick} 
			className={className}
			style={{
				padding: 'var(--space-3) var(--space-3)',
				borderRadius: 'var(--radius)',
				backgroundColor: 'transparent',
				color: 'var(--text)',
				fontSize: '14px',
				fontFamily: 'var(--font-sans)',
				cursor: 'pointer',
				transition: 'var(--transition-fast)',
				...props.style
			}}
			onMouseEnter={(e) => {
				e.target.style.backgroundColor = 'var(--panel-hover)'
			}}
			onMouseLeave={(e) => {
				e.target.style.backgroundColor = 'transparent'
			}}
			{...props}
		>
			{children}
		</div>
	)
}


