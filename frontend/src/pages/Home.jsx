import React from 'react'
import SearchBar from '../components/SearchBar.jsx'
import TickerBar from '../components/TickerBar.jsx'
import AddToWatchlist from '../components/AddToWatchlist.jsx'
import Watchlist from '../components/Watchlist.jsx'

export default function HomePage() {
	return (
		<main className="container">
			<section className="card" style={{width:'100%', maxWidth:900}}>
				<h1 style={{marginBottom:16}}>Home</h1>
				<div style={{display:'flex', flexDirection:'column', gap:16}}>
					<SearchBar />
					<TickerBar />
					<AddToWatchlist onAdded={() => { /* optional refresh hook */ }} />
					<Watchlist />
				</div>
			</section>
		</main>
	)
}
