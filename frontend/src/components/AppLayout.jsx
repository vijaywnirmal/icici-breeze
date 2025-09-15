import React from 'react'
import TickerBar from './TickerBar'

export default function AppLayout({ children }) {
	return (
		<div className="app-layout">
			<TickerBar />
			<div className="main-content">
				{children}
			</div>
		</div>
	)
}
