import React, { useEffect, useRef, useState } from 'react'

export function Dropdown({ trigger, children, align = 'right' }) {
	const [open, setOpen] = useState(false)
	const ref = useRef(null)

	useEffect(() => {
		function onDoc(e) { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
		if (open) document.addEventListener('mousedown', onDoc)
		return () => document.removeEventListener('mousedown', onDoc)
	}, [open])

	return (
		<div className="relative" ref={ref}>
			<div onClick={() => setOpen(v => !v)} className="cursor-pointer select-none">
				{typeof trigger === 'function' ? trigger({ open }) : trigger}
			</div>
			{open && (
				<div className={`absolute mt-2 min-w-[220px] bg-card border border-white/10 rounded-2xl shadow-soft p-2 ${align === 'right' ? 'right-0' : 'left-0'}`}>
					{typeof children === 'function' ? children({ close: () => setOpen(false) }) : children}
				</div>
			)}
		</div>
	)
}

export function DropdownItem({ className = '', children, onClick }) {
	return (
		<div onClick={onClick} className={`px-3 py-2 rounded-xl hover:bg-white/5 text-sm text-slate-200 cursor-pointer ${className}`}>
			{children}
		</div>
	)
}


