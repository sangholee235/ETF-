import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import BotPanel from './BotPanel'
import type { Account, BuyingPower, Holdings } from './types'

const fmt = (v: string | number | null | undefined) =>
  v == null ? '-' : Number(v).toLocaleString()
const pct = (v: string | null | undefined) =>
  v == null ? '-' : (Number(v) * 100).toFixed(2) + '%'
const signClass = (v: string | null | undefined) =>
  v == null ? '' : Number(v) >= 0 ? 'up' : 'down'

const LABEL: Record<string, string> = { toss: '토스증권', kiwoom: '키움증권' }

/** ETF 자동매수 메인 화면: 증권사별(토스/키움)로 나눠 계좌 + 적립봇을 한 곳에서. */
export default function AutoPage() {
  const [brokers, setBrokers] = useState<string[]>([])
  const [broker, setBroker] = useState<string>('')

  useEffect(() => {
    api.brokers()
      .then((r) => {
        setBrokers(r.brokers)
        setBroker((prev) => prev || r.default || r.brokers[0] || '')
      })
      .catch(() => {})
  }, [])

  if (!broker) return <section className="card">증권사 불러오는 중...</section>

  return (
    <>
      <section className="card span2" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        {brokers.map((b) => (
          <button key={b} onClick={() => setBroker(b)}
                  className={broker === b ? 'on' : ''}
                  style={{ background: broker === b ? '#3182f6' : '#2a2a33' }}>
            {LABEL[b] ?? b}
          </button>
        ))}
      </section>

      <AccountHeader broker={broker} />
      <BotPanel key={broker} broker={broker} focused />
    </>
  )
}

function AccountHeader({ broker }: { broker: string }) {
  const [acc, setAcc] = useState<Account | null>(null)
  const [holdings, setHoldings] = useState<Holdings | null>(null)
  const [bp, setBp] = useState<BuyingPower | null>(null)
  const [err, setErr] = useState('')

  const load = useCallback(async () => {
    setErr('')
    try {
      const [a, h, b] = await Promise.all([
        api.accounts(broker).then((x) => x[0] ?? null).catch(() => null),
        api.holdings(broker).catch(() => null),
        api.buyingPower('KRW', broker).catch(() => null),
      ])
      setAcc(a)
      setHoldings(h)
      setBp(b)
      if (!a && !h) setErr('계좌 조회 실패 (키 또는 IP 등록 확인)')
    } catch (e) {
      setErr(String(e instanceof Error ? e.message : e))
    }
  }, [broker])

  useEffect(() => { load() }, [load])

  return (
    <section className="card span2 hero">
      <div className="hero-main">
        <div className="muted">평가자산 (KRW)</div>
        <div className="hero-amount">{fmt(holdings?.marketValue.amount.krw)}<span className="won">원</span></div>
        {holdings && (
          <div className={`hero-pl ${signClass(holdings.profitLoss.amount.krw)}`}>
            {Number(holdings.profitLoss.amount.krw) >= 0 ? '▲' : '▼'} {fmt(Math.abs(Number(holdings.profitLoss.amount.krw)))}원
            {' '}({pct(holdings.profitLoss.rate)})
          </div>
        )}
        {err && <div className="err" style={{ marginTop: 6 }}>{err}</div>}
      </div>
      <div className="hero-sub">
        <Stat label="계좌번호" value={acc?.accountNo ?? '-'} />
        <Stat label="매수가능(KRW)" value={fmt(bp?.cashBuyingPower)} />
        <Stat label="보유 종목수" value={String(holdings?.items.length ?? 0) + '개'} />
      </div>
    </section>
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
