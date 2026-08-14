import { useEffect, useState } from 'react'
import { api } from './api'
import AvgPriceChart from './AvgPriceChart'
import type { BacktestResult } from './types'

const fmt = (v: number) => Math.round(v).toLocaleString()

export default function Backtest({ symbol, name, broker }: { symbol: string; name?: string; broker?: string }) {
  const [days, setDays] = useState(120)
  const [discount, setDiscount] = useState(0.5) // %
  const [fallback, setFallback] = useState(5)
  const [commission, setCommission] = useState(0.015) // % (국내 ETF 기본)
  const [res, setRes] = useState<BacktestResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  async function run() {
    setBusy(true)
    setErr('')
    try {
      setRes(await api.botBacktest(symbol, days, discount / 100, fallback, commission / 100, broker))
    } catch (e) {
      setErr(String(e instanceof Error ? e.message : e))
    } finally {
      setBusy(false)
    }
  }

  const limitBetter = res?.lowerAvgPrice === 'limit'

  return (
    <section className="card">
      <div className="card-head">
        <h2>백테스트 <span className="muted" style={{ fontWeight: 400 }}>· {name ?? symbol}</span></h2>
      </div>
      <div className="row" style={{ alignItems: 'flex-end' }}>
        <Field label="기간(일)" value={days} step={30} onChange={setDays} />
        <Field label="지정가 할인(%)" value={discount} step={0.1} onChange={setDiscount} />
        <Field label="시장가 전환(일)" value={fallback} step={1} onChange={setFallback} />
        <Field label="수수료(%)" value={commission} step={0.005} onChange={setCommission} />
        <button onClick={run} disabled={busy}>{busy ? '계산 중...' : '백테스트 실행'}</button>
      </div>
      {err && <p className="err" style={{ marginTop: 10 }}>{err}</p>}

      {res && (
        <>
          <p className="muted" style={{ marginTop: 14 }}>
            {res.period.from} ~ {res.period.to} ({res.period.days}일), 종가 {fmt(res.lastClose)}원
          </p>
          <div className="table-scroll">
            <table>
              <thead>
                <tr><th>전략</th><th>매수일</th><th>보유</th><th>평단</th><th>투입</th><th>평가액</th><th>수익률</th></tr>
              </thead>
              <tbody>
                <tr className={limitBetter ? 'selected' : ''}>
                  <td>지정가 적립{limitBetter && <span className="check"> ✓</span>}</td>
                  <td>{res.strategyLimit.buys}/{res.strategyLimit.tradingDays}</td>
                  <td>{res.strategyLimit.shares}주</td>
                  <td>{fmt(res.strategyLimit.avgPrice)}</td>
                  <td>{fmt(res.strategyLimit.invested)}</td>
                  <td>{fmt(res.strategyLimit.marketValue)}</td>
                  <td className={res.strategyLimit.returnPct >= 0 ? 'up' : 'down'}>
                    {res.strategyLimit.returnPct}%
                  </td>
                </tr>
                <tr className={!limitBetter ? 'selected' : ''}>
                  <td>단순 매일 적립{!limitBetter && <span className="check"> ✓</span>}</td>
                  <td>{res.strategyDaily.buys}/{res.strategyDaily.buys}</td>
                  <td>{res.strategyDaily.shares}주</td>
                  <td>{fmt(res.strategyDaily.avgPrice)}</td>
                  <td>{fmt(res.strategyDaily.invested)}</td>
                  <td>{fmt(res.strategyDaily.marketValue)}</td>
                  <td className={res.strategyDaily.returnPct >= 0 ? 'up' : 'down'}>
                    {res.strategyDaily.returnPct}%
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="muted" style={{ marginTop: 10 }}>
            평단이 낮은 쪽: <b style={{ color: 'var(--accent)' }}>{limitBetter ? '지정가 적립' : '단순 매일 적립'}</b>.
            {' '}지정가는 {res.strategyLimit.marketFallbacks}회 시장가 전환됨. (매수 수수료 {commission}% 반영 · 매수전용이라 매도세 없음)
          </p>
          {res.series.length > 0 && <AvgPriceChart series={res.series} />}
        </>
      )}
    </section>
  )
}

function Field({ label, value, step, onChange }: {
  label: string; value: number; step: number; onChange: (v: number) => void
}) {
  // 문자열로 따로 들고 있다가 숫자로 파싱되는 시점에만 부모로 올린다. value를 그대로
  // input에 바인딩하면 지우고 새로 입력하는 중간(빈 문자열)에 Number('')=0으로 즉시
  // 되돌아가버려서, 정수부 자릿수를 늘려 입력하는 게 사실상 불가능했던 문제를 고쳤다.
  const [text, setText] = useState(String(value))

  useEffect(() => {
    // 외부(리셋 등)에서 value가 바뀐 경우에만 동기화 — 타이핑 중엔 건드리지 않는다.
    if (Number(text) !== value) setText(String(value))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value])

  const commit = (raw: string) => {
    setText(raw)
    if (raw === '' || raw === '-') return
    const n = Number(raw)
    if (!Number.isNaN(n)) onChange(n)
  }

  return (
    <div className="stat">
      <div className="muted">{label}</div>
      <input type="number" step={step} value={text}
             onChange={(e) => commit(e.target.value)}
             onBlur={() => { if (text === '' || text === '-' || Number.isNaN(Number(text))) setText(String(value)) }}
             style={{ width: 120, marginTop: 4 }} />
    </div>
  )
}
