import { useCallback, useEffect, useRef, useState } from 'react'
import { api, loadQuotes } from './api'
import type { Account, BuyingPower, Holdings, Quote } from './types'
import BotPanel from './BotPanel'
import Chart from './Chart'
import HoldingsDonut from './HoldingsDonut'
import LogsPanel from './LogsPanel'
import './App.css'

const fmt = (v: string | number | null | undefined) =>
  v == null ? '-' : Number(v).toLocaleString()
const pct = (v: string | null | undefined) =>
  v == null ? '-' : (Number(v) * 100).toFixed(2) + '%'
const signClass = (v: string | null | undefined) =>
  v == null ? '' : Number(v) >= 0 ? 'up' : 'down'

export default function App() {
  const initialTab = (['bot', 'logs'].includes(location.hash.slice(1))
    ? location.hash.slice(1)
    : 'view') as 'view' | 'bot' | 'logs'
  const [tab, setTabState] = useState<'view' | 'bot' | 'logs'>(initialTab)
  const setTab = (t: 'view' | 'bot' | 'logs') => {
    setTabState(t)
    history.replaceState(null, '', t === 'view' ? location.pathname : `#${t}`)
  }
  const [symbols, setSymbols] = useState(() => localStorage.getItem('symbols') || '005930,000660,AAPL')
  const [selected, setSelected] = useState(() => localStorage.getItem('selected') || '005930')

  useEffect(() => { localStorage.setItem('symbols', symbols) }, [symbols])
  useEffect(() => { localStorage.setItem('selected', selected) }, [selected])
  const [auto, setAuto] = useState(true)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [loaded, setLoaded] = useState(false)
  const [connected, setConnected] = useState(true)

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
      setLoaded(true)
      setConnected(true)
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e))
      setStatus('')
      setConnected(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  useEffect(() => {
    if (!auto) return
    const t = setInterval(refresh, 8000)
    return () => clearInterval(t)
  }, [auto, refresh])

  const acc = accounts[0]

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <svg width="22" height="22" viewBox="0 0 64 64">
              <rect width="64" height="64" rx="16" fill="currentColor" />
              <path d="M14 40 L26 28 L34 36 L50 20" fill="none" stroke="#fff" strokeWidth="6"
                    strokeLinecap="round" strokeLinejoin="round" />
              <circle cx="50" cy="20" r="5" fill="#fff" />
            </svg>
          </span>
          <span className="brand-name">toss<b>invest</b></span>
        </div>
        <nav className="top-tabs">
          <button className={`tab ${tab === 'view' ? 'on' : ''}`} onClick={() => setTab('view')}>조회</button>
          <button className={`tab ${tab === 'bot' ? 'on' : ''}`} onClick={() => setTab('bot')}>적립봇</button>
          <button className={`tab ${tab === 'logs' ? 'on' : ''}`} onClick={() => setTab('logs')}>로그</button>
        </nav>
        <span className="conn spacer" title={connected ? '백엔드 연결됨' : '백엔드 연결 끊김'}>
          <span className={`dot ${connected ? 'ok' : 'bad'}`} />
          {connected ? '연결됨' : '연결 끊김'}
        </span>
        <span className="muted" style={{ fontSize: 12 }}>{tab === 'view' ? status : ''}</span>
      </header>

      {tab === 'bot' ? (
        <main className="single"><BotPanel /></main>
      ) : tab === 'logs' ? (
        <main className="view-grid"><LogsPanel /></main>
      ) : (
      <main className="view-grid">
        <section className="card toolbar span2">
          <input
            value={symbols}
            onChange={(e) => setSymbols(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && refresh()}
            placeholder="005930,000660,AAPL"
          />
          <button onClick={refresh}>조회</button>
          <label className="muted">
            <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} /> 자동
          </label>
          {error && <span className="err">{error}</span>}
        </section>

        <section className="card span2 hero">
          <div className="hero-main">
            <div className="muted">내 평가자산 (KRW)</div>
            {loaded ? (
              <div className="hero-amount">{fmt(holdings?.marketValue.amount.krw)}<span className="won">원</span></div>
            ) : (
              <div className="hero-amount"><span className="skel" style={{ width: 180, height: 30 }} /></div>
            )}
            {holdings && (
              <div className={`hero-pl ${signClass(holdings.profitLoss.amount.krw)}`}>
                {Number(holdings.profitLoss.amount.krw) >= 0 ? '▲' : '▼'} {fmt(Math.abs(Number(holdings.profitLoss.amount.krw)))}원
                {' '}({pct(holdings.profitLoss.rate)})
              </div>
            )}
          </div>
          <div className="hero-sub">
            <Stat label="계좌번호" value={acc?.accountNo ?? '-'} />
            <Stat label="매수가능(KRW)" value={fmt(bpKrw?.cashBuyingPower)} />
            <Stat label="매수가능(USD)" value={bpUsd ? '$' + fmt(bpUsd.cashBuyingPower) : '-'} />
          </div>
        </section>

        <section className="card">
          <h2>시세 <span className="muted" style={{ fontWeight: 400 }}>· 종목 클릭하면 차트</span></h2>
          <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>종목</th><th>현재가</th><th>통화</th>
                <th>매도1 (가/잔량)</th><th>매수1 (가/잔량)</th><th>시각</th>
              </tr>
            </thead>
            <tbody>
              {!loaded && quotes.length === 0 &&
                Array.from({ length: 3 }).map((_, i) => (
                  <tr key={`s${i}`}>
                    <td><span className="skel" style={{ width: 110, height: 16 }} /></td>
                    <td><span className="skel" style={{ width: 70, height: 16 }} /></td>
                    <td><span className="skel" style={{ width: 30, height: 16 }} /></td>
                    <td><span className="skel" style={{ width: 90, height: 16 }} /></td>
                    <td><span className="skel" style={{ width: 90, height: 16 }} /></td>
                    <td><span className="skel" style={{ width: 50, height: 16 }} /></td>
                  </tr>
                ))}
              {quotes.map((q) => (
                <tr key={q.symbol}
                    className={`clickable ${q.symbol === selected ? 'selected' : ''}`}
                    onClick={() => setSelected(q.symbol)}>
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
          </div>
        </section>

        <Chart symbol={selected} name={quotes.find((q) => q.symbol === selected)?.name} />

        <HoldingsDonut holdings={holdings} />

        <section className="card span2">
          <h2>보유 주식</h2>
          <div className="table-scroll">
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
          </div>
        </section>
      </main>
      )}

      <nav className="bottom-nav">
        <button className={tab === 'view' ? 'on' : ''} onClick={() => setTab('view')}>
          <span className="ico">📊</span>조회
        </button>
        <button className={tab === 'bot' ? 'on' : ''} onClick={() => setTab('bot')}>
          <span className="ico">🤖</span>적립봇
        </button>
        <button className={tab === 'logs' ? 'on' : ''} onClick={() => setTab('logs')}>
          <span className="ico">📜</span>로그
        </button>
      </nav>
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
