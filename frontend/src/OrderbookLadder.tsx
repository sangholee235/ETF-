import { useEffect, useState } from 'react'
import { api } from './api'
import type { Orderbook } from './types'

const fmt = (v: string | number) => Math.round(Number(v)).toLocaleString()

/** 호가창 사다리: 매도(위·빨강) / 매수(아래·파랑), 잔량 막대. */
export default function OrderbookLadder({ symbol, name }: { symbol: string; name?: string }) {
  const [ob, setOb] = useState<Orderbook | null>(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    let alive = true
    const load = () =>
      api.orderbook(symbol)
        .then((d) => alive && (setOb(d), setErr('')))
        .catch((e) => alive && setErr(String(e instanceof Error ? e.message : e)))
    load()
    const t = setInterval(load, 5000)
    return () => { alive = false; clearInterval(t) }
  }, [symbol])

  const asks = (ob?.asks ?? []).slice(0, 10)
  const bids = (ob?.bids ?? []).slice(0, 10)
  const maxVol = Math.max(1, ...asks.map((a) => Number(a.volume)), ...bids.map((b) => Number(b.volume)))

  // 매도호가는 높은가격이 위로 (역순 표시)
  const asksDesc = [...asks].reverse()

  return (
    <section className="card">
      <h2>호가 <span className="muted" style={{ fontWeight: 400 }}>· {name ?? symbol}</span></h2>
      {err && <p className="err">{err}</p>}
      <div className="ob">
        {asksDesc.map((a, i) => (
          <Row key={`a${i}`} side="ask" price={a.price} vol={a.volume} maxVol={maxVol} />
        ))}
        <div className="ob-mid">{bids[0] && asks[0]
          ? `스프레드 ${fmt(Number(asks[0].price) - Number(bids[0].price))}` : '—'}</div>
        {bids.map((b, i) => (
          <Row key={`b${i}`} side="bid" price={b.price} vol={b.volume} maxVol={maxVol} />
        ))}
      </div>
    </section>
  )
}

function Row({ side, price, vol, maxVol }: {
  side: 'ask' | 'bid'; price: string; vol: string; maxVol: number
}) {
  const pct = (Number(vol) / maxVol) * 100
  return (
    <div className={`ob-row ${side}`}>
      <span className="ob-vol-bar" style={{ width: `${pct}%` }} />
      <span className="ob-price">{fmt(price)}</span>
      <span className="ob-vol">{fmt(vol)}</span>
    </div>
  )
}
