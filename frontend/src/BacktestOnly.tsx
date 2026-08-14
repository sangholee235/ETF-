import { useEffect, useState } from 'react'
import { api } from './api'
import Backtest from './Backtest'
import type { BotStatus } from './types'

/** '적립봇' 탭 전용 — 실전 설정/스케줄/로그 등은 다 빼고 백테스트 화면만 보여준다.
 *  대표 종목(포트폴리오 첫 종목)만 알아야 해서 botStatus를 가볍게 조회한다. */
export default function BacktestOnly({ broker }: { broker?: string } = {}) {
  const [status, setStatus] = useState<BotStatus | null>(null)
  const [msg, setMsg] = useState('')

  useEffect(() => {
    api.botStatus(broker)
      .then(setStatus)
      .catch((e) => setMsg(String(e instanceof Error ? e.message : e)))
  }, [broker])

  if (!status) return <div className="card">불러오는 중... {msg && <span className="err">{msg}</span>}</div>

  const cfg = status.config
  const repSymbol = cfg.portfolio?.[0]?.symbol ?? cfg.symbol
  const repName = cfg.portfolio?.[0]?.name ?? cfg.symbol_name

  return <Backtest symbol={repSymbol} name={repName} broker={broker} />
}
