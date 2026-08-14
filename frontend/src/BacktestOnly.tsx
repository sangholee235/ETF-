import { useEffect, useState } from 'react'
import { api } from './api'
import Backtest from './Backtest'

/** '적립봇' 탭 전용 — 실전 설정/스케줄/로그 등은 다 빼고 백테스트 화면만 보여준다.
 *  토스/키움처럼 브로커별로 포트폴리오·종목이 다르므로, AutoPage와 같은 방식으로
 *  브로커 선택 탭을 두고 고른 브로커 기준으로 대표 종목(포트폴리오 첫 종목)을 조회한다. */
export default function BacktestOnly() {
  const [brokers, setBrokers] = useState<string[]>([])
  const [broker, setBroker] = useState('')

  useEffect(() => {
    api.brokers().then((r) => {
      setBrokers(r.brokers)
      setBroker((p) => p || (r.brokers.includes('kiwoom') ? 'kiwoom' : r.default) || r.brokers[0] || '')
    })
  }, [])

  if (!broker) return <div className="card">불러오는 중...</div>

  return (
    <>
      <section className="card span2 broker-bar">
        {brokers.map((b) => (
          <button key={b} onClick={() => setBroker(b)} className={`broker-btn ${broker === b ? 'on' : ''}`}>
            {b === 'kiwoom' ? '키움증권' : b === 'toss' ? '토스증권' : b}
          </button>
        ))}
      </section>
      <BacktestForBroker key={broker} broker={broker} />
    </>
  )
}

function BacktestForBroker({ broker }: { broker: string }) {
  const [repSymbol, setRepSymbol] = useState<string | null>(null)
  const [repName, setRepName] = useState<string | undefined>(undefined)
  const [msg, setMsg] = useState('')

  useEffect(() => {
    api.botStatus(broker)
      .then((status) => {
        const cfg = status.config
        setRepSymbol(cfg.portfolio?.[0]?.symbol ?? cfg.symbol)
        setRepName(cfg.portfolio?.[0]?.name ?? cfg.symbol_name)
      })
      .catch((e) => setMsg(String(e instanceof Error ? e.message : e)))
  }, [broker])

  if (!repSymbol) return <div className="card">불러오는 중... {msg && <span className="err">{msg}</span>}</div>

  return <Backtest symbol={repSymbol} name={repName} broker={broker} />
}
