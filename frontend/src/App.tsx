import { useCallback, useEffect, useRef, useState } from 'react'
import { api, loadQuotes } from './api'
import type { Account, BuyingPower, Holdings, Quote } from './types'
import './App.css'

const fmt = (v: string | number | null | undefined) =>
  v == null ? '-' : Number(v).toLocaleString()
const pct = (v: string | null | undefined) =>
  v == null ? '-' : (Number(v) * 100).toFixed(2) + '%'
const signClass = (v: string | null | undefined) =>
  v == null ? '' : Number(v) >= 0 ? 'up' : 'down'

export default function App() {
  const [symbols, setSymbols] = useState('005930,000660,AAPL')
  const [auto, setAuto] = useState(true)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')

  const [accounts, setAccounts] = useState<Account[]>([])
  const [quotes, setQuotes] = useState<Quote[]>([])
  const [holdings, setHoldings] = useState<Holdings | null>(null)
  const [bpKrw, setBpKrw] = useState<BuyingPower | null>(null)
  const [bpUsd, setBpUsd] = useState<BuyingPower | null>(null)

  const symbolsRef = useRef(symbols)
  symbolsRef.current = symbols

  const refresh = useCallback(async () => {
    setStatus('조회 중...')
    setError('')
    try {
      const [acc, q, h, bk, bu] = await Promise.all([
        api.accounts(),
        loadQuotes(symbolsRef.current),
        api.holdings().catch(() => null),
        api.buyingPower('KRW').catch(() => null),
        api.buyingPower('USD').catch(() => null),
      ])
      setAccounts(acc)
      setQuotes(q)
      setHoldings(h)
      setBpKrw(bk)
      setBpUsd(bu)
      setStatus('갱신: ' + new Date().toLocaleTimeString())
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e))
      setStatus('')
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  useEffect(() => {
    if (!auto) return
    const t = setInterval(refresh, 5000)
    return () => clearInterval(t)
  }, [auto, refresh])

  const acc = accounts[0]

  return (
    <div className="wrap">
      <header>
        <h1>토스 조회 대시보드</h1>
        <input
          value={symbols}
          onChange={(e) => setSymbols(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && refresh()}
          placeholder="005930,000660,AAPL"
        />
        <button onClick={refresh}>조회</button>
        <label className="muted">
          <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} /> 자동(5초)
        </label>
        <span className="muted">{status}</span>
        {error && <span className="err">오류: {error}</span>}
      </header>

      <main>
        <section className="card">
          <h2>계좌 / 잔고</h2>
          <div className="row">
            <Stat label="계좌번호" value={acc?.accountNo ?? '-'} />
            <Stat label="평가금액(KRW)" value={fmt(holdings?.marketValue.amount.krw)} />
            <Stat label="매수가능(KRW)" value={fmt(bpKrw?.cashBuyingPower)} />
            <Stat label="매수가능(USD)" value={bpUsd ? '$' + fmt(bpUsd.cashBuyingPower) : '-'} />
          </div>
        </section>

        <section className="card">
          <h2>시세</h2>
          <table>
            <thead>
              <tr>
                <th>종목</th><th>현재가</th><th>통화</th>
                <th>매도1 (가/잔량)</th><th>매수1 (가/잔량)</th><th>시각</th>
              </tr>
            </thead>
            <tbody>
              {quotes.map((q) => (
                <tr key={q.symbol}>
                  <td>{q.name} <span className="muted">{q.symbol}</span></td>
                  <td className="big">{fmt(q.lastPrice)}</td>
                  <td>{q.currency ?? '-'}</td>
                  <td>{q.ask1 ? `${fmt(q.ask1.price)} / ${fmt(q.ask1.volume)}` : '-'}</td>
                  <td>{q.bid1 ? `${fmt(q.bid1.price)} / ${fmt(q.bid1.volume)}` : '-'}</td>
                  <td className="muted">{q.timestamp ? new Date(q.timestamp).toLocaleTimeString() : '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section className="card">
          <h2>보유 주식</h2>
          <table>
            <thead>
              <tr>
                <th>종목</th><th>수량</th><th>평균단가</th><th>현재가</th>
                <th>평가금액</th><th>손익</th><th>손익률</th>
              </tr>
            </thead>
            <tbody>
              {holdings && holdings.items.length > 0 ? (
                holdings.items.map((it) => (
                  <tr key={it.symbol}>
                    <td>{it.name} <span className="muted">{it.symbol}</span></td>
                    <td>{fmt(it.quantity)}</td>
                    <td>{fmt(it.averagePurchasePrice)}</td>
                    <td>{fmt(it.lastPrice)}</td>
                    <td>{fmt(it.marketValue.amount)}</td>
                    <td className={signClass(it.profitLoss.amount)}>{fmt(it.profitLoss.amount)}</td>
                    <td className={signClass(it.profitLoss.rate)}>{pct(it.profitLoss.rate)}</td>
                  </tr>
                ))
              ) : (
                <tr><td colSpan={7} className="muted">보유 종목 없음</td></tr>
              )}
            </tbody>
          </table>
        </section>
      </main>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat">
      <div className="muted">{label}</div>
      <div className="big">{value}</div>
    </div>
  )
}
