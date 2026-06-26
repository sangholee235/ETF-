import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import type { BotLog } from './types'

type Filter = 'all' | 'buy' | 'skip'

export default function LogsPanel() {
  const [logs, setLogs] = useState<BotLog[]>([])
  const [filter, setFilter] = useState<Filter>('all')
  const [err, setErr] = useState('')

  const load = useCallback(async () => {
    try {
      setLogs(await api.botLogs(300))
    } catch (e) {
      setErr(String(e instanceof Error ? e.message : e))
    }
  }, [])

  useEffect(() => {
    load()
    const t = setInterval(load, 10000)
    return () => clearInterval(t)
  }, [load])

  const shown = logs.filter((l) =>
    filter === 'all' ? true : filter === 'buy' ? l.action !== 'SKIP' : l.action === 'SKIP',
  )

  const buys = logs.filter((l) => l.action !== 'SKIP').length

  return (
    <>
      <section className="card span2">
        <div className="card-head">
          <h2>실행 로그</h2>
          <div className="seg">
            <button className={filter === 'all' ? 'on' : ''} onClick={() => setFilter('all')}>전체</button>
            <button className={filter === 'buy' ? 'on' : ''} onClick={() => setFilter('buy')}>매수</button>
            <button className={filter === 'skip' ? 'on' : ''} onClick={() => setFilter('skip')}>건너뜀</button>
          </div>
        </div>
        <p className="muted">총 {logs.length}건 · 매수/시도 {buys}건 · 10초마다 갱신</p>
        {err && <p className="err">{err}</p>}
      </section>

      <section className="card span2">
        <div className="table-scroll">
          <table>
            <thead>
              <tr><th>시각</th><th>모드</th><th>액션</th><th>가격</th><th>체결</th><th>사유</th></tr>
            </thead>
            <tbody>
              {shown.length === 0 ? (
                <tr><td colSpan={6} className="muted">기록 없음</td></tr>
              ) : (
                shown.map((lg, i) => (
                  <tr key={i}>
                    <td className="muted">{lg.ts.slice(0, 19).replace('T', ' ')}</td>
                    <td>
                      <span style={{ color: lg.mode === 'LIVE' ? 'var(--up)' : 'var(--muted)' }}>
                        {lg.mode}
                      </span>
                    </td>
                    <td>{actionLabel(lg.action)}</td>
                    <td>{lg.price == null ? '-' : Number(lg.price).toLocaleString()}</td>
                    <td>{lg.filled == null ? '-' : lg.filled ? '✅' : '❌'}</td>
                    <td className="muted">{lg.reason}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </>
  )
}

function actionLabel(a: string): string {
  if (a === 'LIMIT_BUY') return '지정가 매수'
  if (a === 'MARKET_BUY') return '시장가 매수'
  if (a === 'SKIP') return '건너뜀'
  return a
}
