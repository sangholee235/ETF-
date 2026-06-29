import { useState } from 'react'
import type { BotConfig, EtfCatalogItem, PortfolioItem, PortfolioProgress, WaterfallStatus } from './types'

const COLORS = ['#3182f6', '#f5a623', '#22c55e', '#f04452', '#a855f7', '#06b6d4', '#eab308', '#ec4899']
const fmt = (v: number) => Math.round(v).toLocaleString()

export default function PortfolioPanel({
  cfg, catalog, onPatch, busy, progress, waterfall, nextSymbol,
}: {
  cfg: BotConfig
  catalog: EtfCatalogItem[]
  onPatch: (p: Partial<BotConfig>) => void
  busy: boolean
  progress?: PortfolioProgress[]
  waterfall?: WaterfallStatus[]
  nextSymbol?: string
}) {
  const [items, setItems] = useState<PortfolioItem[]>(cfg.portfolio ?? [])
  const [addSym, setAddSym] = useState('')
  const [dragIdx, setDragIdx] = useState<number | null>(null)
  const mode = cfg.fill_mode ?? 'weight'
  const dirty = JSON.stringify(items) !== JSON.stringify(cfg.portfolio ?? [])
  const priceOf = (sym: string) => {
    const p = catalog.find((e) => e.symbol === sym)?.lastPrice
    return p ? Number(p) : null
  }

  const add = () => {
    const c = catalog.find((e) => e.symbol === addSym)
    if (!c || items.some((i) => i.symbol === c.symbol)) return
    setItems([...items, { symbol: c.symbol, name: c.name, weight: 10, target: 100000 }])
    setAddSym('')
  }
  const setField = (sym: string, k: 'weight' | 'target', v: number) =>
    setItems(items.map((i) => (i.symbol === sym ? { ...i, [k]: v } : i)))
  const remove = (sym: string) => setItems(items.filter((i) => i.symbol !== sym))

  const reorder = (from: number, to: number) => {
    if (from === to) return
    const next = [...items]
    const [m] = next.splice(from, 1)
    next.splice(to, 0, m)
    setItems(next)
  }

  return (
    <section className="card span2">
      <div className="card-head">
        <h2>적립 ETF / 목표 비중</h2>
      </div>

      {/* 우선순위(워터폴) 모드는 잠시 숨김 — 비중추종만 사용 (코드는 유지) */}
      {mode === 'waterfall'
        ? <Waterfall items={items} wf={waterfall} dragIdx={dragIdx} setDragIdx={setDragIdx}
                     reorder={reorder} setField={setField} remove={remove} priceOf={priceOf} />
        : <Weight items={items} progress={progress} setField={setField} remove={remove}
                  priceOf={priceOf} nextSymbol={nextSymbol} />}

      <div className="pf-add">
        <select value={addSym} onChange={(e) => setAddSym(e.target.value)}>
          <option value="">+ ETF 추가</option>
          {catalog.filter((e) => !items.some((i) => i.symbol === e.symbol)).map((e) => (
            <option key={e.symbol} value={e.symbol}>
              {e.name} ({e.symbol}){e.lastPrice ? ` · 1주 ${Number(e.lastPrice).toLocaleString()}원` : ''}
            </option>
          ))}
        </select>
        <button onClick={add} disabled={!addSym}>추가</button>
        <button onClick={() => onPatch({ portfolio: items })} disabled={busy || !dirty} style={{ marginLeft: 'auto' }}>저장</button>
      </div>

      <p className="muted" style={{ marginTop: 10 }}>
        {mode === 'waterfall'
          ? <>위에서부터 <b style={{ color: 'var(--txt)' }}>목표 금액까지 채우고</b> 다음 ETF로 내려갑니다. 드래그로 우선순위를 바꾸세요.</>
          : <><b style={{ color: 'var(--txt)' }}>목표 비중을 유지</b>하되, 매수가능금액으로 <b style={{ color: 'var(--txt)' }}>살 수 있는 ETF 중 가장 부족한 걸</b> 삽니다. (돈 되는 대로 비중에 수렴)</>}
      </p>

      {mode === 'weight' && (
        <div className="wait-toggle">
          <div>
            <div style={{ fontWeight: 600 }}>돈 모자랄 때 — 가장 부족한(비싼) ETF를 못 사면?</div>
            <div className="muted" style={{ fontSize: 12.5 }}>
              {cfg.wait_for_underweight
                ? '지금: 기다림 — 그것만 사려고 현금을 모읍니다 (비중 정확 유지).'
                : '지금: 살 수 있는 거라도 산다 — 다른 목표미달 ETF를 매수합니다 (돈 안 놀림).'}
            </div>
          </div>
          <div className="seg">
            <button className={!cfg.wait_for_underweight ? 'on' : ''} disabled={busy}
                    onClick={() => onPatch({ wait_for_underweight: false })}>살 수 있는 거라도 산다</button>
            <button className={cfg.wait_for_underweight ? 'on' : ''} disabled={busy}
                    onClick={() => onPatch({ wait_for_underweight: true })}>기다린다</button>
          </div>
        </div>
      )}
    </section>
  )
}

/* ─────────── 우선순위 워터폴 ─────────── */
function Waterfall({ items, wf, dragIdx, setDragIdx, reorder, setField, remove, priceOf }: {
  items: PortfolioItem[]; wf?: WaterfallStatus[]; dragIdx: number | null
  setDragIdx: (n: number | null) => void; reorder: (f: number, t: number) => void
  setField: (s: string, k: 'weight' | 'target', v: number) => void; remove: (s: string) => void
  priceOf: (sym: string) => number | null
}) {
  const wfMap = new Map((wf ?? []).map((w) => [w.symbol, w]))
  const badge = (s?: string) => s === 'done' ? <span className="wf-badge done">✅ 완료</span>
    : s === 'active' ? <span className="wf-badge active">⏳ 적립 중</span>
    : <span className="wf-badge wait">⬜ 대기</span>

  if (items.length === 0) return <div className="muted" style={{ padding: '8px 0' }}>아래에서 ETF를 추가하고 목표 금액을 정하세요.</div>
  return (
    <div className="wf-list">
      {items.map((it, i) => {
        const w = wfMap.get(it.symbol)
        return (
          <div key={it.symbol} className={`wf-row ${dragIdx === i ? 'dragging' : ''}`} draggable
               onDragStart={() => setDragIdx(i)}
               onDragOver={(e) => { e.preventDefault(); if (dragIdx !== null && dragIdx !== i) { reorder(dragIdx, i); setDragIdx(i) } }}
               onDragEnd={() => setDragIdx(null)}>
            <span className="wf-grip">⠿</span>
            <span className="wf-pri">{i + 1}</span>
            <div className="wf-main">
              <div className="wf-name">{it.name} <span className="muted">{it.symbol}</span>
                {priceOf(it.symbol) != null && <span className="muted" style={{ fontWeight: 400 }}> · 1주 {fmt(priceOf(it.symbol)!)}원</span>}
                {' '}{badge(w?.status)}</div>
              <div className="wf-bar"><div className="wf-bar-fill" style={{ width: `${Math.min(100, (w?.fillPct ?? 0) * 100)}%` }} /></div>
              <div className="muted wf-amt">{fmt(w?.investedKrw ?? 0)} / {fmt(it.target ?? 0)}원</div>
            </div>
            <label className="wf-target muted">목표(원)
              <input type="number" value={it.target ?? 0} min={0} step={10000}
                     onChange={(e) => setField(it.symbol, 'target', Number(e.target.value))} style={{ width: 110 }} />
            </label>
            <button className="ghost" onClick={() => remove(it.symbol)}>✕</button>
          </div>
        )
      })}
    </div>
  )
}

/* ─────────── 비중 추종 (도넛) ─────────── */
function Weight({ items, progress, setField, remove, priceOf, nextSymbol }: {
  items: PortfolioItem[]; progress?: PortfolioProgress[]
  setField: (s: string, k: 'weight' | 'target', v: number) => void; remove: (s: string) => void
  priceOf: (sym: string) => number | null; nextSymbol?: string
}) {
  const progMap = new Map((progress ?? []).map((p) => [p.symbol, p]))
  const totalWeight = items.reduce((s, i) => s + Number(i.weight || 0), 0)
  const size = 150, r = 58, stroke = 22, c = 2 * Math.PI * r
  let offset = 0
  const valid = items.filter((i) => Number(i.weight) > 0)

  return (
    <div className="donut-wrap">
      {valid.length > 0 ? (
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="donut">
          <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
            {valid.map((it, i) => {
              const dash = (Number(it.weight) / (totalWeight || 1)) * c
              const el = <circle key={it.symbol} cx={size / 2} cy={size / 2} r={r} fill="none"
                stroke={COLORS[i % COLORS.length]} strokeWidth={stroke}
                strokeDasharray={`${dash} ${c - dash}`} strokeDashoffset={-offset} />
              offset += dash
              return el
            })}
          </g>
        </svg>
      ) : <div className="muted" style={{ padding: 20 }}>ETF를 추가해 목표 비중을 정하세요.</div>}

      <div style={{ flex: '1 1 260px', minWidth: 0 }}>
        {items.map((it, i) => {
          const pr = progMap.get(it.symbol)
          const target = totalWeight > 0 ? Number(it.weight) / totalWeight : 0
          const current = pr?.currentWeight ?? 0
          return (
            <div key={it.symbol} className="pf-row-wrap">
              <div className="pf-row">
                <i style={{ background: COLORS[i % COLORS.length] }} />
                <span className="nm">{it.name} <span className="muted">{it.symbol}{priceOf(it.symbol) != null ? ` · 1주 ${fmt(priceOf(it.symbol)!)}원` : ''}</span></span>
                <input type="number" value={it.weight} min={0} step={5}
                       onChange={(e) => setField(it.symbol, 'weight', Number(e.target.value))} style={{ width: 64 }} />
                <span className="muted">%</span>
                <button className="ghost" onClick={() => remove(it.symbol)}>✕</button>
              </div>
              {(() => {
                const gap = (target - current) * 100   // %p (양수=부족, 음수=초과)
                const isNext = nextSymbol === it.symbol
                const badge = Math.abs(gap) < 0.5
                  ? <span className="gap-badge bal">균형</span>
                  : gap > 0
                    ? <span className="gap-badge under">목표까지 {gap.toFixed(0)}%p 부족</span>
                    : <span className="gap-badge over">목표보다 {(-gap).toFixed(0)}%p 초과</span>
                return (
                  <div className="pf-prog">
                    <div className="pf-bar">
                      <div className="pf-bar-fill" style={{ width: `${Math.min(100, current * 100)}%`, background: COLORS[i % COLORS.length] }} />
                      <div className="pf-bar-target" style={{ left: `${Math.min(100, target * 100)}%` }} />
                    </div>
                    <span className="pf-prog-txt">
                      <span className="muted">현재 {(current * 100).toFixed(0)}% / 목표 {(target * 100).toFixed(0)}% · {fmt(pr?.investedKrw ?? 0)}원</span>
                      {' '}{badge}
                      {isNext && <span className="gap-badge next">⬅ 다음 적립</span>}
                    </span>
                  </div>
                )
              })()}
            </div>
          )
        })}
        {totalWeight !== 100 && items.length > 0 && <p className="muted warn" style={{ marginTop: 8 }}>합계 {totalWeight}% (100% 권장 — 자동 정규화됨)</p>}
      </div>
    </div>
  )
}
