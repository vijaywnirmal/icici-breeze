import '../src/styles.css'
import '../src/components/TickerBar.css'
import TickerBar from '../src/components/TickerBar.jsx'

export default function App({ Component, pageProps }) {
	return (
		<div className="app-layout">
			<TickerBar />
			<div className="main-content">
				<Component {...pageProps} />
			</div>
		</div>
	)
}

