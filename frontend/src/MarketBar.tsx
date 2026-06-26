import { useEffect, useState } from 'react'
import { api } from './api'
import type { IndexSummary } from './types'

const fmt = (v: number | null) => (v == null ? '-' : Math.round(v).toLocaleString())

export default function MarketBar({ onPick }: { onPick?: (symbol: string, name: string) => void }) {
  const [idx, setIdx] = useState<IndexSummary[]>([])

  useEffect(() => {
    const load = () => api.marketSummary().then(setIdx).catch(() => {})
    load()
    const t = setInterval(load, 60000)
    return () => clearInterval(t)
  }, [])

  return (
    <section className="card span2 marketbar">
      {idx.map((x) => {
        const up = (x.changePct ?? 0) >= 0
        return (
          <button key={x.symbol} className="idx" onClick={() => onPick?.(x.symbol, x.label)}>
            <div className="idx-head">
              <span className="idx-label">{x.label}</span>
              <span className="muted idx-proxy">{x.proxy}</span>
            </div>
            <div className="idx-price">{fmt(x.lastPrice)}</div>
            <div className={`idx-chg ${up ? 'up' : 'down'}`}>
              {x.changePct == null ? '-' : `${up ? '▲' : '▼'} ${Math.abs(x.changePct).toFixed(2)}%`}
            </div>
            <Spark data={x.spark} up={up} />
          </button>
        )
      })}
    </section>
  )
}

function Spark({ data, up }: { data: number[]; up: boolean }) {
  const w = 120, h = 34
  if (!data || data.length < 2) return <svg width={w} height={h} />
  const min = Math.min(...data), max = Math.max(...data)
  const range = max - min || 1
  const pts = data
    .map((v, i) => `${(i / (data.length - 1)) * w},${h - ((v - min) / range) * (h - 4) - 2}`)
    .join(' ')
  const color = up ? '#f04452' : '#4d9fff'
  return (
    <svg width={w} height={h} className="spark">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5"
                strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  )
}
