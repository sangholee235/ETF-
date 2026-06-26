import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import Backtest from './Backtest'
import Chart from './Chart'
import PortfolioPanel from './PortfolioPanel'
import Sweep from './Sweep'
import type { BotStatus, EtfCatalogItem } from './types'

const fmt = (v: number | string | null | undefined) =>
  v == null ? '-' : Number(v).toLocaleString()

export default function BotPanel() {
  const [status, setStatus] = useState<BotStatus | null>(null)
  const [catalog, setCatalog] = useState<EtfCatalogItem[]>([])
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try {
      const [s, c] = await Promise.all([api.botStatus(), api.botCatalog()])
      setStatus(s)
      setCatalog(c)
    } catch (e) {
      setMsg(String(e instanceof Error ? e.message : e))
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const cfg = status?.config
  const st = status?.state

  async function patch(p: Parameters<typeof api.botPatchConfig>[0]) {
    setBusy(true)
    setMsg('')
    try {
      await api.botPatchConfig(p)
      await load()
    } catch (e) {
      setMsg(String(e instanceof Error ? e.message : e))
    } finally {
      setBusy(false)
    }
  }

  async function runTick() {
    setBusy(true)
    setMsg('실행 중...')
    try {
      const r = await api.botRun()
      const d = (r.decision ?? {}) as { action?: string; reason?: string }
      setMsg(`결과: ${d.action} — ${d.reason}`)
      await load()
    } catch (e) {
      setMsg(String(e instanceof Error ? e.message : e))
    } finally {
      setBusy(false)
    }
  }

  if (!cfg || !st) return <div className="card">불러오는 중... {msg && <span className="err">{msg}</span>}</div>

  const dailyTooSmall = (() => {
    const sel = catalog.find((e) => e.symbol === cfg.symbol)
    const price = sel?.lastPrice ? Number(sel.lastPrice) : null
    return price != null && price * cfg.quantity_per_buy > cfg.daily_budget_krw
  })()

  return (
    <>
      <section className="card">
        <h2>적립봇 상태</h2>
        <div className="row">
          <Stat label="모드" value={cfg.dry_run ? 'DRY_RUN (모의)' : 'LIVE (실주문)'} danger={!cfg.dry_run} />
          <Stat label="가동" value={cfg.enabled ? 'ON' : 'OFF(정지)'} danger={!cfg.enabled} />
          <Stat label="대상" value={`${cfg.symbol_name} (${cfg.symbol})`} />
          <Stat label="누적 투입(추정)" value={fmt(st.totalInvestedKrw) + '원'} />
          <Stat label="보유 수량(추정)" value={fmt(st.totalFilledQty) + '주'} />
          <Stat label="연속 미체결" value={`${st.consecutiveMisses} / ${cfg.fallback_after_misses}일`} />
        </div>
        <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <button onClick={runTick} disabled={busy}>지금 1회 실행</button>
          <button onClick={() => patch({ dry_run: !cfg.dry_run })} disabled={busy}
                  style={{ background: cfg.dry_run ? '#e8590c' : '#2b8a3e' }}>
            {cfg.dry_run ? 'LIVE 전환(실주문 켜기)' : 'DRY_RUN 전환(실주문 끄기)'}
          </button>
          <button onClick={() => patch({ enabled: !cfg.enabled })} disabled={busy}
                  style={{ background: cfg.enabled ? '#c92a2a' : '#3182f6' }}>
            {cfg.enabled ? '봇 정지(킬스위치)' : '봇 가동'}
          </button>
          {msg && <span className="muted">{msg}</span>}
        </div>
        {!cfg.dry_run && (
          <p className="err" style={{ marginTop: 10 }}>
            ⚠ LIVE 모드입니다. 실제 돈으로 주문이 나갑니다.
          </p>
        )}
        {dailyTooSmall && (
          <p className="err" style={{ marginTop: 10 }}>
            ⚠ 1주 가격이 하루 한도({fmt(cfg.daily_budget_krw)}원)보다 큽니다. 매수가 차단됩니다 — 한도를 올리거나 저가 ETF를 고르세요.
          </p>
        )}
      </section>

      <section className="card">
        <h2>대상 ETF <span className="muted" style={{ fontWeight: 400 }}>· 행을 눌러 선택</span></h2>
        <div className="table-scroll">
        <table>
          <thead>
            <tr><th>ETF</th><th>분류</th><th>현재가</th><th>세금</th><th></th></tr>
          </thead>
          <tbody>
            {catalog.map((e) => (
              <tr key={e.symbol}
                  className={`clickable ${e.symbol === cfg.symbol ? 'selected' : ''}`}
                  onClick={() => !busy && e.symbol !== cfg.symbol && patch({ symbol: e.symbol, symbol_name: e.name })}>
                <td>{e.name} <span className="muted">{e.symbol}</span></td>
                <td>{e.category}</td>
                <td>{fmt(e.lastPrice)}</td>
                <td className="muted">{e.tax === 'exempt' ? '비과세' : '15.4% 과세'}</td>
                <td>{e.symbol === cfg.symbol ? <span className="check">✓</span> : ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </section>

      <PortfolioPanel cfg={cfg} catalog={catalog} onPatch={patch} busy={busy} />

      <section className="card">
        <h2>전략 / 한도</h2>
        <div className="row">
          <NumField label="1회 수량(주)" value={cfg.quantity_per_buy}
                    onSave={(v) => patch({ quantity_per_buy: v })} />
          <NumField label="지정가 할인(%)" value={cfg.discount_pct * 100} step={0.1}
                    onSave={(v) => patch({ discount_pct: v / 100 })} />
          <NumField label="시장가 전환(연속미체결 일수)" value={cfg.fallback_after_misses}
                    onSave={(v) => patch({ fallback_after_misses: v })} />
          <NumField label="하루 한도(원)" value={cfg.daily_budget_krw} step={10000}
                    onSave={(v) => patch({ daily_budget_krw: v })} />
        </div>
        <p className="muted" style={{ marginTop: 8 }}>누적 한도: 무제한 (하루 한도만 적용)</p>
      </section>

      <section className="card">
        <h2>자동 적립 스케줄</h2>
        <div className="row" style={{ alignItems: 'center' }}>
          <div className="stat">
            <div className="muted">자동 적립</div>
            <button onClick={() => patch({ schedule_enabled: !cfg.schedule_enabled })} disabled={busy}
                    style={{ marginTop: 4, background: cfg.schedule_enabled ? '#2b8a3e' : '#3a3a44' }}>
              {cfg.schedule_enabled ? 'ON (자동)' : 'OFF (수동)'}
            </button>
          </div>
          <div className="stat">
            <div className="muted">실행 시각 (평일, KST)</div>
            <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
              <input type="time" defaultValue={cfg.schedule_time}
                     onBlur={(e) => e.target.value !== cfg.schedule_time && patch({ schedule_time: e.target.value })}
                     style={{ width: 130 }} />
            </div>
          </div>
        </div>
        <p className="muted" style={{ marginTop: 8 }}>
          {cfg.schedule_enabled
            ? `매 평일 ${cfg.schedule_time}에 자동 적립 (백엔드가 켜져 있어야 동작).`
            : 'OFF: "지금 1회 실행" 버튼으로만 매수합니다.'}
          {' '}하루 1회 가드레일로 중복 매수는 방지됩니다.
        </p>
      </section>

      <Backtest symbol={cfg.symbol} name={cfg.symbol_name} />
      <Sweep symbol={cfg.symbol} name={cfg.symbol_name} days={120} />
      <Chart symbol={cfg.symbol} name={cfg.symbol_name} />

      <section className="card">
        <h2>실행 로그 (최근 30건)</h2>
        <div className="table-scroll">
        <table>
          <thead>
            <tr><th>시각</th><th>모드</th><th>액션</th><th>가격</th><th>체결</th><th>사유</th></tr>
          </thead>
          <tbody>
            {st.logs.length === 0 ? (
              <tr><td colSpan={6} className="muted">아직 실행 기록 없음</td></tr>
            ) : (
              [...st.logs].reverse().map((lg, i) => (
                <tr key={i}>
                  <td className="muted">{lg.ts.slice(0, 19).replace('T', ' ')}</td>
                  <td>{lg.mode}</td>
                  <td>{lg.action}</td>
                  <td>{fmt(lg.price)}</td>
                  <td>{lg.filled == null ? '-' : lg.filled ? '✅' : '❌'}</td>
                  <td className="muted">{lg.reason}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
        </div>
      </section>
    </>
  )
}

function Stat({ label, value, danger }: { label: string; value: string; danger?: boolean }) {
  return (
    <div className="stat">
      <div className="muted">{label}</div>
      <div className="big" style={danger ? { color: 'var(--up)' } : undefined}>{value}</div>
    </div>
  )
}

function NumField({ label, value, step = 1, onSave }: {
  label: string; value: number; step?: number; onSave: (v: number) => void
}) {
  const [v, setV] = useState(String(value))
  useEffect(() => setV(String(value)), [value])
  return (
    <div className="stat">
      <div className="muted">{label}</div>
      <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
        <input type="number" step={step} value={v} onChange={(e) => setV(e.target.value)}
               style={{ width: 110 }} />
        <button onClick={() => onSave(Number(v))} disabled={Number(v) === value}>저장</button>
      </div>
    </div>
  )
}
