import React, { useState } from 'react'

export default function SearchBar() {
	const [text, setText] = useState('')
	return (
		<div style={{display:'flex', gap:8, alignItems:'center'}}>
			<input
				type="text"
				placeholder="Search stocks (coming soon)"
				value={text}
				onChange={(e) => setText(e.target.value)}
				style={{
					flex:1,
					padding:'10px 12px',
					borderRadius:10,
					border:'1px solid rgba(255,255,255,0.08)',
					background:'#0f141d',
					color:'var(--text)'
				}}
			/>
			<button type="button" disabled title="Stock search coming soon" style={{width:'auto'}}>
				Search
			</button>
		</div>
	)
}
