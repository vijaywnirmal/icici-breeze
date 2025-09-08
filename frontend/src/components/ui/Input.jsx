import React from 'react'

export default function Input({ className = '', ...props }) {
	return (
		<input
			className={`bg-white/5 border border-white/10 rounded-2xl px-3 h-10 text-sm text-white placeholder:text-slate-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition ${className}`}
			{...props}
		/>
	)
}


