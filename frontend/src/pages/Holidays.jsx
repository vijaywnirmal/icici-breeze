import React, { useEffect, useMemo, useState } from 'react'

export default function HolidaysPage() {
	const [holidays, setHolidays] = useState([])
	const [loading, setLoading] = useState(true)
	const [error, setError] = useState('')
	const [selectedYear, setSelectedYear] = useState(2025)
	const [refreshing, setRefreshing] = useState(false)

	const apiBase = import.meta.env.VITE_API_BASE_URL || ''
	const api = useMemo(() => (apiBase || '').replace(/\/$/, ''), [apiBase])

	// Load holidays when component mounts or year changes
	useEffect(() => {
		loadHolidays()
	}, [selectedYear])

	const loadHolidays = async () => {
		setLoading(true)
		setError('')
		try {
			const response = await fetch(`${api}/api/market/holidays?year=${selectedYear}`)
			const data = await response.json()
			
			if (data.count > 0) {
				setHolidays(data.items || [])
			} else {
				setHolidays([])
				setError(data.message || `No holidays found for year ${selectedYear}`)
			}
		} catch (err) {
			setError(err?.message || 'Failed to load holidays')
			setHolidays([])
		} finally {
			setLoading(false)
		}
	}

	const handleRefresh = async () => {
		if (selectedYear !== 2025) {
			setError('Refresh is only available for 2025 (current year)')
			return
		}

		setRefreshing(true)
		setError('')
		try {
			const response = await fetch(`${api}/api/market/holidays/refresh`, {
				method: 'POST'
			})
			const data = await response.json()
			
			if (data.success) {
				// Reload holidays after successful refresh
				await loadHolidays()
				setError('')
			} else {
				setError(data.message || 'Failed to refresh holidays')
			}
		} catch (err) {
			setError(err?.message || 'Failed to refresh holidays')
		} finally {
			setRefreshing(false)
		}
	}

	const formatDate = (dateStr) => {
		try {
			const date = new Date(dateStr)
			return date.toLocaleDateString('en-IN', {
				day: '2-digit',
				month: '2-digit',
				year: 'numeric'
			})
		} catch {
			return dateStr
		}
	}

	return (
		<section className="content card" style={{width:'100%', maxWidth:900}}>
			<div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px'}}>
				<h1>NSE Trading Holidays</h1>
				<div style={{display: 'flex', gap: '10px', alignItems: 'center'}}>
					<select 
						value={selectedYear} 
						onChange={(e) => setSelectedYear(parseInt(e.target.value))}
						style={{
							padding: '8px 12px',
							border: '1px solid #ccc',
							borderRadius: '4px',
							backgroundColor: 'white'
						}}
					>
						{Array.from({length: 15}, (_, i) => 2011 + i).map(year => (
							<option key={year} value={year}>{year}</option>
						))}
					</select>
					{selectedYear === 2025 && (
						<button 
							onClick={handleRefresh}
							disabled={refreshing}
							style={{
								padding: '8px 16px',
								backgroundColor: refreshing ? '#ccc' : '#007bff',
								color: 'white',
								border: 'none',
								borderRadius: '4px',
								cursor: refreshing ? 'not-allowed' : 'pointer'
							}}
						>
							{refreshing ? 'Refreshing...' : 'Refresh 2025'}
						</button>
					)}
				</div>
			</div>

			{loading && <div className="message">Loading holidays for {selectedYear}...</div>}
			{error && <div className="message error">{error}</div>}
			
			{!loading && !error && (
				<>
					<div style={{marginBottom: '15px', color: '#666'}}>
						Showing {holidays.length} holidays for {selectedYear}
					</div>
					
					<div style={{overflowX:'auto'}}>
						<table className="table" style={{minWidth:500}}>
							<thead>
								<tr>
									<th style={{textAlign:'left'}}>Date</th>
									<th style={{textAlign:'left'}}>Day</th>
									<th style={{textAlign:'left'}}>Holiday Name</th>
								</tr>
							</thead>
							<tbody>
								{holidays.map((holiday, idx) => (
									<tr key={idx}>
										<td>{formatDate(holiday.date)}</td>
										<td>{holiday.day}</td>
										<td>{holiday.name}</td>
									</tr>
								))}
								{holidays.length === 0 && (
									<tr>
										<td colSpan={3} style={{opacity:0.7, textAlign: 'center', padding: '20px'}}>
											No holidays found for {selectedYear}
										</td>
									</tr>
								)}
							</tbody>
						</table>
					</div>
				</>
			)}
		</section>
	)
}
