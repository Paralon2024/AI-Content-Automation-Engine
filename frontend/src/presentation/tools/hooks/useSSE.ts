import { useState, useEffect } from 'react'

export default function useSSE(url: string | null) {
  const [logs, setLogs] = useState<string[]>([])
  const [done, setDone] = useState(false)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!url) {
      setLogs([])
      setDone(false)
      setFailed(false)
      return
    }

    setLogs([])
    setDone(false)
    setFailed(false)

    const es = new EventSource(url)

    es.onmessage = (e: MessageEvent<string>) => {
      const msg = e.data
      if (msg === '[DONE]') {
        setDone(true)
        es.close()
      } else if (msg === '[FAILED]') {
        setFailed(true)
        es.close()
      } else if (msg !== '[TIMEOUT]') {
        setLogs(prev => [...prev, msg])
      }
    }

    // EventSource reconnects automatically after transient disconnects.
    // Do not mark a job successful (or close the stream) on a network error.
    es.onerror = () => undefined

    return () => es.close()
  }, [url])

  return { logs, done, failed }
}
