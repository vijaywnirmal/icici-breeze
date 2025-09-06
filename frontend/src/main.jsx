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
import Sidebar from './components/Sidebar.jsx'
import TickerBar from './components/TickerBar.jsx'
import CustomerProfile from './components/CustomerProfile.jsx'
import './styles.css'

createRoot(document.getElementById('root')).render(
	<BrowserRouter>
		<Routes>
			<Route path="/" element={<App />} />
			<Route path="/home" element={
				<div className="layout">
					<Sidebar />
					<div>
						<div style={{padding:'18px'}}><TickerBar /></div>
						<HomePage />
					</div>
				</div>
			} />
			<Route path="/holidays" element={
				<div className="layout">
					<Sidebar />
					<div>
						<div style={{padding:'18px'}}><TickerBar /></div>
						<HolidaysPage />
					</div>
				</div>
			} />
			<Route path="/backtest" element={
				<div className="layout">
					<Sidebar />
					<div>
						<div style={{padding:'18px'}}><TickerBar /></div>
						<BacktestPage />
					</div>
				</div>
			} />
			<Route path="/builder" element={
				<div className="layout">
					<Sidebar />
					<div>
						<div style={{padding:'18px'}}><TickerBar /></div>
						<StrategyBuilder />
					</div>
				</div>
			} />
			<Route path="/results" element={
				<div className="layout">
					<Sidebar />
					<div>
						<div style={{padding:'18px'}}><TickerBar /></div>
						<BacktestResults />
					</div>
				</div>
			} />
			<Route path="/live-trading" element={
				<div className="layout">
					<Sidebar />
					<div>
						<div style={{padding:'18px'}}><TickerBar /></div>
						<LiveTrading />
					</div>
				</div>
			} />
			<Route path="*" element={<Navigate to="/" replace />} />
		</Routes>
	</BrowserRouter>
)
