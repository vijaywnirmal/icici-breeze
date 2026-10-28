import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import App from './App.jsx'
import ReactLazy from 'react'
const OptionChain = React.lazy(() => import('./pages/OptionChain.jsx'))
import AppLayout from './components/AppLayout.jsx'
import HomePage from './pages/Home.jsx'
import HolidaysPage from './pages/Holidays.jsx'
import BacktestPage from './pages/Backtest.jsx'
import StrategyBuilder from './pages/StrategyBuilder.tsx'
import BacktestResults from './pages/BacktestResults.tsx'
import './styles.css'

// Silence routine console output per request; warnings and errors still show so failures can be traced
;(() => {
  const noop = () => {}
  // eslint-disable-next-line no-console
  console.log = noop
  // eslint-disable-next-line no-console
  console.debug = noop
  // eslint-disable-next-line no-console
  console.info = noop
})()

createRoot(document.getElementById('root')).render(
	<BrowserRouter>
		<Routes>
			<Route path="/" element={<App />} />
			<Route path="/home" element={
				<AppLayout>
					<HomePage />
				</AppLayout>
			} />
			<Route path="/holidays" element={
				<AppLayout>
					<HolidaysPage />
				</AppLayout>
			} />
			<Route path="/backtest" element={
				<AppLayout>
					<BacktestPage />
				</AppLayout>
			} />
			<Route path="/builder" element={
				<AppLayout>
					<StrategyBuilder />
				</AppLayout>
			} />
			<Route path="/results" element={
				<AppLayout>
					<BacktestResults />
				</AppLayout>
			} />
			<Route path="/option-chain" element={
				<AppLayout>
					<React.Suspense fallback={<div style={{padding:12}}>Loading Option Chain...</div>}>
						<OptionChain />
					</React.Suspense>
				</AppLayout>
			} />
			<Route path="*" element={<Navigate to="/" replace />} />
		</Routes>
	</BrowserRouter>
)
