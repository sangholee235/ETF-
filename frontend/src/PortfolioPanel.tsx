import { useState } from 'react'
import type { BotConfig, EtfCatalogItem, PortfolioItem, PortfolioProgress } from './types'

const COLORS = ['#3182f6', '#f5a623', '#22c55e', '#f04452', '#a855f7', '#06b6d4', '#eab308', '#ec4899']
const fmt = (v: number) => Math.round(v).toLocaleString()

export default function PortfolioPanel({
  cfg, catalog, onPatch, busy, progress,
}: {
  cfg: BotConfig
  catalog: EtfCatalogItem[]
  onPatch: (p: Partial<BotConfig>) => void
  busy: boolean
  progress?: PortfolioProgress[]
}) {
  const [items, setItems] = useState<PortfolioItem[]>(cfg.portfolio ?? [])
  const [addSym, setAddSym] = useState('')
  const progMap = new Map((progress ?? []).map((p) => [p.symbol, p]))
  const hasInvested = (progress ?? []).some((p) => p.investedKrw > 0)

  const totalWeight = items.reduce((s, i) => s + Number(i.weight || 0), 0)
  const dirty = JSON.stringify(items) !== JSON.stringify(cfg.portfolio ?? [])

  const add = () => {
    const c = catalog.find((e) => e.symbol === addSym)
    if (!c || items.some((i) => i.symbol === c.symbol)) return
    setItems([...items, { symbol: c.symbol, name: c.name, weight: 10 }])
    setAddSym('')
  }
  const setWeight = (sym: string, w: number) =>
    setItems(items.map((i) => (i.symbol === sym ? { ...i, weight: w } : i)))
  const remove = (sym: string) => setItems(items.filter((i) => i.symbol !== sym))

  // 도넛 (정규화 비중)
  const size = 150, r = 58, stroke = 22, c = 2 * Math.PI * r
  let offset = 0
  const valid = items.filter((i) => Number(i.weight) > 0)

  return (
    <section className="card span2">
      <div className="card-head">
        <h2>적립 ETF / 목표 비중 <span className="muted" style={{ fontWeight: 400 }}>· 하나만 모으려면 한 종목을 100%로</span></h2>
      </div>

      <div className="donut-wrap">
        {valid.length > 0 ? (
          <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="donut">
            <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
              {valid.map((it, i) => {
                const dash = (Number(it.weight) / (totalWeight || 1)) * c
                const el = (
                  <circle key={it.symbol} cx={size / 2} cy={size / 2} r={r} fill="none"
                          stroke={COLORS[i % COLORS.length]} strokeWidth={stroke}
                          strokeDasharray={`${dash} ${c - dash}`} strokeDashoffset={-offset} />
                )
                offset += dash
                return el
              })}
            </g>
          </svg>
        ) : (
          <div className="muted" style={{ padding: 20 }}>ETF를 추가해 목표 비중을 정하세요.</div>
        )}

        <div style={{ flex: '1 1 260px', minWidth: 0 }}>
          {items.map((it, i) => {
            const pr = progMap.get(it.symbol)
            const target = totalWeight > 0 ? Number(it.weight) / totalWeight : 0
            const current = pr?.currentWeight ?? 0
            return (
            <div key={it.symbol} className="pf-row-wrap">
              <div className="pf-row">
                <i style={{ background: COLORS[i % COLORS.length] }} />
                <span className="nm">{it.name} <span className="muted">{it.symbol}</span></span>
                <input type="number" value={it.weight} min={0} step={5}
                       onChange={(e) => setWeight(it.symbol, Number(e.target.value))}
                       style={{ width: 64 }} />
                <span className="muted">%</span>
                <button className="ghost" onClick={() => remove(it.symbol)}>✕</button>
              </div>
              {hasInvested && (
                <div className="pf-prog" title={`목표 ${(target * 100).toFixed(0)}% · 현재 ${(current * 100).toFixed(0)}%`}>
                  <div className="pf-bar">
                    <div className="pf-bar-fill" style={{ width: `${Math.min(100, current * 100)}%`, background: COLORS[i % COLORS.length] }} />
                    <div className="pf-bar-target" style={{ left: `${Math.min(100, target * 100)}%` }} />
                  </div>
                  <span className="muted pf-prog-txt">
                    현재 {(current * 100).toFixed(0)}% / 목표 {(target * 100).toFixed(0)}% · {fmt(pr?.investedKrw ?? 0)}원
                  </span>
                </div>
              )}
            </div>
          )})}

          <div className="pf-add">
            <select value={addSym} onChange={(e) => setAddSym(e.target.value)}>
              <option value="">+ ETF 추가</option>
              {catalog.filter((e) => !items.some((i) => i.symbol === e.symbol)).map((e) => (
                <option key={e.symbol} value={e.symbol}>{e.name} ({e.symbol})</option>
              ))}
            </select>
            <button onClick={add} disabled={!addSym}>추가</button>
          </div>

          <div style={{ marginTop: 12, display: 'flex', gap: 10, alignItems: 'center' }}>
            <span className={`muted ${totalWeight !== 100 ? 'warn' : ''}`}>
              합계 {totalWeight}% {totalWeight !== 100 && '(100% 권장 — 자동 정규화됨)'}
            </span>
            <button onClick={() => onPatch({ portfolio: items })} disabled={busy || !dirty}>
              저장
            </button>
          </div>
        </div>
      </div>
      <p className="muted" style={{ marginTop: 10 }}>
        매 적립마다 목표 비중 대비 <b style={{ color: 'var(--txt)' }}>가장 부족한 ETF</b>를 1주 매수해 비중에 수렴시킵니다.
      </p>
    </section>
  )
}
