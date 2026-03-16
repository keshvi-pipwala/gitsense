import { useEffect, useRef, useState, useCallback } from 'react'
import { createWebSocket } from '../lib/api'

export function useWebSocket(onMessage) {
  const wsRef = useRef(null)
  const [connected, setConnected] = useState(false)
  const reconnectRef = useRef(null)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return
    const ws = createWebSocket((msg) => {
      if (msg.type !== 'pong') onMessage(msg)
    })
    ws.onopen = () => setConnected(true)
    ws.onclose = () => {
      setConnected(false)
      reconnectRef.current = setTimeout(connect, 3000)
    }
    wsRef.current = ws
  }, [onMessage])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  return { connected }
}
