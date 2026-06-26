import { useEffect, useState } from 'react'
import { api } from './api'
import type { Holdings } from './types'

const COLORS = ['#3182f6', '#f5a623', '#22c55e', '#f04452', '#a855f7', '#06b6d4', '#eab308', '#ec4899']
const fmt = (v: number) => Math.round(v).toLocaleString()

interface Slice {
  symbol: string
  name: string
  krw: number
  pct: number
  color: string
}

export default function HoldingsDonut({ holdings }: { holdings: Holdings | null }) {
  const [rate, setRate] = useState(1350) // USD->KRW 폴백

  useEffect(() => {
    api.exchangeRate().then((r) => setRate(Number(r.rate) || 1350)).catch(() => {})
  }, [])

  const items = holdings?.items ?? []
  const valued = items.map((it) => ({
    symbol: it.symbol,
    name: it.name,
    krw: Number(it.marketValue.amount) * (it.currency === 'USD' ? rate : 1),
  }))
  const total = valued.reduce((s, v) => s + v.krw, 0)

  if (!items.length || total <= 0) {
    return (
      <section className="card span2">
        <h2>보유 비중</h2>
        <p className="muted">보유 종목이 없어요. 적립을 시작하면 여기에 비중이 표시됩니다.</p>
      </section>
    )
  }

  const slices: Slice[] = valued
    .map((v, i) => ({ ...v, pct: v.krw / total, color: COLORS[i % COLORS.length] }))
    .sort((a, b) => b.pct - a.pct)

  // SVG 도넛
  const size = 180
  const r = 70
  const stroke = 26
  const c = 2 * Math.PI * r
  let offset = 0

  return (
    <section className="card span2">
      <h2>보유 비중</h2>
      <div className="donut-wrap">
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="donut">
          <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
            {slices.map((s) => {
              const dash = s.pct * c
              const el = (
                <circle key={s.symbol} cx={size / 2} cy={size / 2} r={r} fill="none"
                        stroke={s.color} strokeWidth={stroke}
                        strokeDasharray={`${dash} ${c - dash}`} strokeDashoffset={-offset} />
              )
              offset += dash
              return el
            })}
          </g>
          <text x="50%" y="46%" textAnchor="middle" className="donut-total-label">평가자산</text>
          <text x="50%" y="58%" textAnchor="middle" className="donut-total">{fmt(total)}원</text>
        </svg>

        <ul className="donut-legend">
          {slices.map((s) => (
            <li key={s.symbol}>
              <i style={{ background: s.color }} />
              <span className="nm">{s.name} <span className="muted">{s.symbol}</span></span>
              <span className="pc">{(s.pct * 100).toFixed(1)}%</span>
              <span className="amt muted">{fmt(s.krw)}원</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
