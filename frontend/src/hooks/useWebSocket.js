import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

/**
 * useWebSocket - shared WebSocket hook with simple pub/sub helpers
 * - Single connection per URL per hook instance
 * - Auto-reconnect with exponential backoff (optional)
 * - Exposes send/subscribe/unsubscribe and connection state
 */
export default function useWebSocket(url, options = {}) {
  const { autoConnect = false, reconnect = true, maxRetries = 5 } = options

  const wsRef = useRef(null)
  const listenersRef = useRef(new Set())
  const retriesRef = useRef(0)
  const reconnectTimer = useRef(null)

  const [readyState, setReadyState] = useState(WebSocket.CLOSED)
  const isOpen = readyState === WebSocket.OPEN

  const connect = useCallback(() => {
    if (!url) return
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return
    }
    try {
      const ws = new WebSocket(url)
      wsRef.current = ws
      setReadyState(WebSocket.CONNECTING)

      ws.onopen = () => {
        retriesRef.current = 0
        setReadyState(WebSocket.OPEN)
      }

      ws.onmessage = (evt) => {
        let data = null
        try { data = JSON.parse(evt.data) } catch { data = evt.data }
        listenersRef.current.forEach((cb) => {
          try { cb(data) } catch {}
        })
      }

      ws.onerror = () => {
        setReadyState(WebSocket.CLOSING)
      }

      ws.onclose = () => {
        setReadyState(WebSocket.CLOSED)
        if (reconnect && retriesRef.current < maxRetries) {
          const delay = Math.min(30000, 1000 * Math.pow(2, retriesRef.current))
          retriesRef.current += 1
          clearTimeout(reconnectTimer.current)
          reconnectTimer.current = setTimeout(() => connect(), delay)
        }
      }
    } catch {
      // ignore
    }
  }, [url, reconnect, maxRetries])

  const disconnect = useCallback(() => {
    try { wsRef.current?.close() } catch {}
    setReadyState(WebSocket.CLOSED)
  }, [])

  const send = useCallback((obj) => {
    try {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(typeof obj === 'string' ? obj : JSON.stringify(obj))
      }
    } catch {}
  }, [])

  const subscribe = useCallback((symbols) => {
    if (!Array.isArray(symbols) || symbols.length === 0) return
    send({ action: 'subscribe_many', symbols })
  }, [send])

  const unsubscribe = useCallback((symbols) => {
    if (!Array.isArray(symbols) || symbols.length === 0) return
    send({ action: 'unsubscribe_many', symbols })
  }, [send])

  const addMessageListener = useCallback((cb) => {
    listenersRef.current.add(cb)
    return () => listenersRef.current.delete(cb)
  }, [])

  useEffect(() => {
    if (autoConnect) connect()
    return () => {
      clearTimeout(reconnectTimer.current)
      try { wsRef.current?.close() } catch {}
      listenersRef.current.clear()
    }
  }, [autoConnect, connect])

  return useMemo(() => ({
    wsRef,
    isOpen,
    readyState,
    connect,
    disconnect,
    send,
    subscribe,
    unsubscribe,
    addMessageListener,
  }), [isOpen, readyState, connect, disconnect, send, subscribe, unsubscribe, addMessageListener])
}


