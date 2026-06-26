import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import Chart from './Chart'
import MarketBar from './MarketBar'
import OrderbookLadder from './OrderbookLadder'
import type { RankItem } from './types'

type Sort = 'value' | 'up' | 'down' | 'volume'
const fmt = (v: number | null) => (v == null ? '-' : Math.round(v).toLocaleString())

const won = (v: number | null) => {
  if (v == null) return '-'
  if (v >= 1e12) return (v / 1e12).toFixed(1) + '조'
  if (v >= 1e8) return Math.round(v / 1e8).toLocaleString() + '억'
  return Math.round(v).toLocaleString()
}

export default function RankingPanel() {
  const [items, setItems] = useState<RankItem[]>([])
  const [sort, setSort] = useState<Sort>('value')
  const [selected, setSelected] = useState<RankItem | null>(null)
  const [err, setErr] = useState('')

  const load = useCallback(async () => {
    try {
      const data = await api.ranking()
      setItems(data)
      setSelected((s) => {
        if (!s) return data[0] ?? null
        return data.find((d) => d.symbol === s.symbol) ?? s // 가격 갱신
      })
    } catch (e) {
      setErr(String(e instanceof Error ? e.message : e))
    }
  }, [])

  useEffect(() => {
    load()
    const t = setInterval(load, 30000)
    return () => clearInterval(t)
  }, [load])

  const sorted = [...items].sort((a, b) => {
    if (sort === 'value') return (b.value ?? 0) - (a.value ?? 0)
    if (sort === 'volume') return (b.volume ?? 0) - (a.volume ?? 0)
    const av = a.changePct ?? -999, bv = b.changePct ?? -999
    return sort === 'up' ? bv - av : av - bv
  })

  return (
    <>
      <MarketBar onPick={(symbol, name) => {
        const found = items.find((d) => d.symbol === symbol)
        setSelected(found ?? ({ symbol, name } as RankItem))
      }} />

      {/* 선택 종목 헤더 */}
      {selected && (
        <section className="card span2 stock-head">
          <div>
            <div className="sh-name">{selected.name} <span className="muted">{selected.symbol}</span></div>
            <div className="sh-price">{fmt(selected.lastPrice)}<span className="won">원</span></div>
          </div>
          {selected.changePct != null && (
            <div className={`sh-chg ${selected.changePct >= 0 ? 'up' : 'down'}`}>
              {selected.changePct >= 0 ? '▲' : '▼'} {Math.abs(selected.changePct).toFixed(2)}%
            </div>
          )}
          <div className="sh-meta muted">
            <span>거래대금 {won(selected.value)}</span>
            <span>시총 {won(selected.marketCap)}</span>
          </div>
        </section>
      )}

      {/* 차트(위) + 호가(옆) */}
      {selected && <Chart symbol={selected.symbol} name={selected.name} />}
      {selected && <OrderbookLadder symbol={selected.symbol} name={selected.name} />}

      {/* 랭킹 표 */}
      <section className="card span2">
        <div className="card-head">
          <h2>실시간 차트 <span className="muted" style={{ fontWeight: 400 }}>· 주요 20종목 · 30초 갱신</span></h2>
          <div className="seg">
            <button className={sort === 'value' ? 'on' : ''} onClick={() => setSort('value')}>거래대금</button>
            <button className={sort === 'up' ? 'on' : ''} onClick={() => setSort('up')}>급상승</button>
            <button className={sort === 'down' ? 'on' : ''} onClick={() => setSort('down')}>급하락</button>
            <button className={sort === 'volume' ? 'on' : ''} onClick={() => setSort('volume')}>거래량</button>
          </div>
        </div>
        {err && <p className="err">{err}</p>}
        <div className="table-scroll">
          <table>
            <thead>
              <tr><th>#</th><th>종목</th><th>현재가</th><th>등락률</th><th>거래대금</th><th>시가총액</th><th>거래량</th></tr>
            </thead>
            <tbody>
              {sorted.map((it, i) => (
                <tr key={it.symbol}
                    className={`clickable ${selected?.symbol === it.symbol ? 'selected' : ''}`}
                    onClick={() => setSelected(it)}>
                  <td className="muted">{i + 1}</td>
                  <td>{it.name} <span className="muted">{it.symbol}</span></td>
                  <td className="big">{fmt(it.lastPrice)}</td>
                  <td className={it.changePct == null ? 'muted' : it.changePct >= 0 ? 'up' : 'down'}>
                    {it.changePct == null ? '-' : `${it.changePct >= 0 ? '▲' : '▼'} ${Math.abs(it.changePct).toFixed(2)}%`}
                  </td>
                  <td>{won(it.value)}</td>
                  <td className="muted">{won(it.marketCap)}</td>
                  <td className="muted">{fmt(it.volume)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  )
}
