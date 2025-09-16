import React, { useCallback, useEffect, useMemo, useState } from 'react'
import useWebSocket from '../hooks/useWebSocket'

export default function OptionChain() {
  const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
  const wsBase = import.meta.env.VITE_API_BASE_WS || ''
  const wsUrl = useMemo(() => {
    const base = (wsBase || apiBase).replace(/\/$/, '')
    if (base.startsWith('ws://') || base.startsWith('wss://')) return `${base}/ws/stocks`
    if (base.startsWith('http://')) return `ws://${base.substring('http://'.length)}/ws/stocks`
    if (base.startsWith('https://')) return `wss://${base.substring('https://'.length)}/ws/stocks`
    return 'ws://127.0.0.1:8000/ws/stocks'
  }, [apiBase, wsBase])

  const { isOpen, connect, subscribe, addMessageListener } = useWebSocket(wsUrl, { autoConnect: true })
  const [items, setItems] = useState([])
  const [query, setQuery] = useState('NIFTY')
  const [loading, setLoading] = useState(false)

  const fetchOptions = useCallback(async () => {
    setLoading(true)
    try {
      const url = `${apiBase}/api/instruments/live-trading?q=${encodeURIComponent(query)}&limit=50`
      const res = await fetch(url)
      const json = await res.json().catch(() => ({}))
      if (json && json.success && Array.isArray(json.items)) {
        setItems(json.items)
        if (isOpen) {
          const symbols = json.items.map(it => ({
            stock_code: (it.stock_code || it.symbol || '').toUpperCase(),
            token: it.token,
            exchange_code: it.exchange_code || 'NSE',
            product_type: 'cash',
          }))
          subscribe(symbols)
        }
      } else {
        setItems([])
      }
    } catch {
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [apiBase, query, isOpen, subscribe])

  useEffect(() => {
    const off = addMessageListener((msg) => {
      // Option chain component can react to ticks if needed in future
    })
    return () => off()
  }, [addMessageListener])

  useEffect(() => { fetchOptions() }, [fetchOptions])

  return (
    <div style={{ padding: 16 }}>
      <h2>Option Chain</h2>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search underlying" />
        <button onClick={fetchOptions} disabled={loading}>{loading ? 'Loading...' : 'Search'}</button>
        <button onClick={connect} disabled={isOpen}>{isOpen ? 'Connected' : 'Connect WS'}</button>
      </div>
      <div style={{ maxHeight: 420, overflow: 'auto', border: '1px solid #eee', borderRadius: 6 }}>
        {items.length === 0 ? (
          <div style={{ padding: 12 }}>No items</div>
        ) : (
          <table style={{ width: '100%', fontSize: 14 }}>
            <thead>
              <tr>
                <th style={{ textAlign: 'left', padding: 8 }}>Symbol</th>
                <th style={{ textAlign: 'left', padding: 8 }}>Company</th>
                <th style={{ textAlign: 'left', padding: 8 }}>Token</th>
                <th style={{ textAlign: 'left', padding: 8 }}>Exchange</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) => (
                <tr key={`${it.symbol}-${it.token}`}>
                  <td style={{ padding: 8 }}>{it.symbol}</td>
                  <td style={{ padding: 8 }}>{it.company_name}</td>
                  <td style={{ padding: 8 }}>{it.token}</td>
                  <td style={{ padding: 8 }}>{it.exchange_code || it.exchange}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}


