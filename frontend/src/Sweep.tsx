import { useState } from 'react'
import { api } from './api'
import type { SweepResult } from './types'

const fmt = (v: number) => Math.round(v).toLocaleString()

export default function Sweep({ symbol, name, days }: { symbol: string; name?: string; days: number }) {
  const [res, setRes] = useState<SweepResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  async function run() {
    setBusy(true)
    setErr('')
    try {
      setRes(await api.botSweep(symbol, days, 0.00015)) // 국내 ETF 0.015% 수수료 반영
    } catch (e) {
      setErr(String(e instanceof Error ? e.message : e))
    } finally {
      setBusy(false)
    }
  }

  // 기준선(단순적립)이 모든 지정가 조합보다 평단이 낮은가?
  const baselineWins = res ? res.results.every((r) => r.avgPrice >= res.baselineDaily.avgPrice) : false

  return (
    <section className="card">
      <div className="card-head">
        <h2>파라미터 스윕 <span className="muted" style={{ fontWeight: 400 }}>· {name ?? symbol} · 최근 {days}일</span></h2>
        <button onClick={run} disabled={busy}>{busy ? '계산 중...' : '최적값 탐색'}</button>
      </div>
      {err && <p className="err">{err}</p>}

      {res && (
        <>
          <p className="muted">
            단순 매일 적립 기준 평단 <b style={{ color: 'var(--txt)' }}>{fmt(res.baselineDaily.avgPrice)}</b>
            {' '}/ 수익률 {res.baselineDaily.returnPct}%
            {baselineWins && <span className="up"> · 이 기간엔 단순 적립이 모든 지정가 조합보다 우수</span>}
          </p>
          <div className="table-scroll">
            <table>
              <thead>
                <tr><th>순위</th><th>할인%</th><th>전환일</th><th>평단</th><th>수익률</th><th>체결</th><th>시장가</th></tr>
              </thead>
              <tbody>
                {res.results.map((r, i) => (
                  <tr key={i} className={i === 0 ? 'selected' : ''}>
                    <td>{i + 1}{i === 0 && <span className="check"> ★</span>}</td>
                    <td>{r.discountPct}%</td>
                    <td>{r.fallback}일</td>
                    <td>{fmt(r.avgPrice)}</td>
                    <td className={r.returnPct >= 0 ? 'up' : 'down'}>{r.returnPct}%</td>
                    <td>{r.buys}</td>
                    <td>{r.marketFallbacks}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted" style={{ marginTop: 8 }}>
            평단이 낮은 순. ★ = 최적 조합. 평단은 적게 사도 낮아질 수 있으니 체결 횟수도 함께 보세요. (수수료·세금 미반영)
          </p>
        </>
      )}
    </section>
  )
}
