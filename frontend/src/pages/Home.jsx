import React from 'react'
import TickerBar from '../components/TickerBar.jsx'

export default function HomePage() {
	return (
		<main className="container">
			<section className="card" style={{width:'100%', maxWidth:900}}>
				<h1 style={{marginBottom:16}}>Home</h1>
				<div style={{display:'flex', flexDirection:'column', gap:16}}>
					<TickerBar />
				</div>
			</section>
		</main>
	)
}
