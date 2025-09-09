import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import App from './App.jsx'
import HomePage from './pages/Home.jsx'
import HolidaysPage from './pages/Holidays.jsx'
import BacktestPage from './pages/Backtest.jsx'
import StrategyBuilder from './pages/StrategyBuilder.tsx'
import BacktestResults from './pages/BacktestResults.tsx'
import LiveTrading from './pages/LiveTrading.jsx'
import TickerBar from './components/TickerBar.jsx'
import CustomerProfile from './components/CustomerProfile.jsx'
import './styles.css'

createRoot(document.getElementById('root')).render(
	<BrowserRouter>
		<Routes>
			<Route path="/" element={<App />} />
			<Route path="/home" element={
				<div className="full-screen-layout">
					<div className="ticker-container">
						<TickerBar />
					</div>
					<HomePage />
				</div>
			} />
			<Route path="/holidays" element={
				<div className="full-screen-layout">
					<div className="ticker-container">
						<TickerBar />
					</div>
					<HolidaysPage />
				</div>
			} />
			<Route path="/backtest" element={
				<div className="full-screen-layout">
					<div className="ticker-container">
						<TickerBar />
					</div>
					<BacktestPage />
				</div>
			} />
			<Route path="/builder" element={
				<div className="full-screen-layout">
					<div className="ticker-container">
						<TickerBar />
					</div>
					<StrategyBuilder />
				</div>
			} />
			<Route path="/results" element={
				<div className="full-screen-layout">
					<div className="ticker-container">
						<TickerBar />
					</div>
					<BacktestResults />
				</div>
			} />
			<Route path="/live-trading" element={
				<div className="full-screen-layout">
					<div className="ticker-container">
						<TickerBar />
					</div>
					<LiveTrading />
				</div>
			} />
			<Route path="*" element={<Navigate to="/" replace />} />
		</Routes>
	</BrowserRouter>
)
