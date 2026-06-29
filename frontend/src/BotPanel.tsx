import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import Backtest from './Backtest'
import Chart from './Chart'
import PortfolioPanel from './PortfolioPanel'
import Sweep from './Sweep'
import type { BotPreview, BotStatus, EtfCatalogItem } from './types'

const fmt = (v: number | string | null | undefined) =>
  v == null ? '-' : Number(v).toLocaleString()

export default function BotPanel({ broker, focused }: { broker?: string; focused?: boolean } = {}) {
  const [status, setStatus] = useState<BotStatus | null>(null)
  const [catalog, setCatalog] = useState<EtfCatalogItem[]>([])
  const [preview, setPreview] = useState<BotPreview | null>(null)
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try {
      const [s, c, p] = await Promise.all([
        api.botStatus(broker),
        api.botCatalog(broker),
        api.botPreview(broker).catch(() => null),
      ])
      setStatus(s)
      setCatalog(c)
      setPreview(p)
    } catch (e) {
      setMsg(String(e instanceof Error ? e.message : e))
    }
  }, [broker])

  useEffect(() => {
    load()
  }, [load])

  const cfg = status?.config
  const st = status?.state

  async function patch(p: Parameters<typeof api.botPatchConfig>[0]) {
    setBusy(true)
    setMsg('')
    try {
      await api.botPatchConfig(p, broker)
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
      const r = await api.botRun(broker)
      const d = (r.decision ?? {}) as { action?: string; reason?: string }
      setMsg(`결과: ${d.action} — ${d.reason}`)
      await load()
    } catch (e) {
      setMsg(String(e instanceof Error ? e.message : e))
    } finally {
      setBusy(false)
    }
  }

  // LIVE 전환은 실주문이라 확인창
  function toggleMode() {
    if (cfg!.dry_run && !window.confirm('LIVE 모드로 전환하면 실제 돈으로 주문이 나갑니다. 계속할까요?')) return
    patch({ dry_run: !cfg!.dry_run })
  }

  if (!cfg || !st) return <div className="card">불러오는 중... {msg && <span className="err">{msg}</span>}</div>

  // 차트/백테스트 대표 종목: 포트폴리오 첫 종목 (없으면 기본)
  const repSymbol = cfg.portfolio?.[0]?.symbol ?? cfg.symbol
  const repName = cfg.portfolio?.[0]?.name ?? cfg.symbol_name
  const pfCount = (cfg.portfolio ?? []).filter((p) => Number(p.weight) > 0).length

  return (
    <>
      <section className="card">
        <h2>적립봇 상태</h2>
        <div className="row">
          <Stat label="모드" value={cfg.dry_run ? 'DRY_RUN (모의)' : 'LIVE (실주문)'} danger={!cfg.dry_run} />
          <Stat label="가동" value={cfg.enabled ? 'ON' : 'OFF(정지)'} danger={!cfg.enabled} />
          <Stat label="적립 대상" value={pfCount > 0 ? `포트폴리오 ${pfCount}종목` : '미설정'} />
          <Stat label="누적 투입(추정)" value={fmt(st.totalInvestedKrw) + '원'} />
          <Stat label="보유 수량(추정)" value={fmt(st.totalFilledQty) + '주'} />
          <Stat label="연속 미체결" value={`${st.consecutiveMisses} / ${cfg.fallback_after_misses}일`} />
        </div>
        <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <button onClick={toggleMode} disabled={busy}
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
      </section>

      <NextBuyCard preview={preview} dryRun={cfg.dry_run} onRun={runTick} busy={busy} />

      <PortfolioPanel cfg={cfg} catalog={catalog} onPatch={patch} busy={busy}
                      progress={preview?.progress} waterfall={preview?.waterfall} />

      <section className="card">
        <h2>전략 / 한도</h2>
        <div className="row">
          <NumField label="1회 수량(주)" value={cfg.quantity_per_buy}
                    hint="한 번 적립할 때 매수하는 주식 수" onSave={(v) => patch({ quantity_per_buy: v })} />
          <NumField label="지정가 할인(%)" value={cfg.discount_pct * 100} step={0.1}
                    hint="전일 종가보다 이만큼 낮은 가격에 지정가 매수 (싸게 사려는 폭)"
                    onSave={(v) => patch({ discount_pct: v / 100 })} />
          <NumField label="시장가 전환(연속미체결 일수)" value={cfg.fallback_after_misses}
                    hint="지정가가 N일 연속 안 잡히면 시장가로 매수 (상승장에서 계속 놓치는 것 방지)"
                    onSave={(v) => patch({ fallback_after_misses: v })} />
          <NumField label="하루 한도(원)" value={cfg.daily_budget_krw} step={10000}
                    hint="하루 1회 매수금액 상한. 1주 가격보다 커야 매수됩니다"
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
                     style={{ width: 190 }} />
            </div>
          </div>
        </div>
        <p className="muted" style={{ marginTop: 8 }}>
          {cfg.schedule_enabled
            ? `매 평일 ${cfg.schedule_time}에 자동 적립 (백엔드가 켜져 있어야 동작).`
            : 'OFF: "지금 1회 적립" 버튼으로만 매수합니다.'}
          {' '}하루 1회 가드레일로 중복 매수는 방지됩니다.
        </p>
      </section>

      {!focused && <>
        <Backtest symbol={repSymbol} name={repName} broker={broker} />
        <Sweep symbol={repSymbol} name={repName} days={120} broker={broker} />
        <Chart symbol={repSymbol} name={repName} broker={broker} />
      </>}

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

function NumField({ label, value, step = 1, hint, onSave }: {
  label: string; value: number; step?: number; hint?: string; onSave: (v: number) => void
}) {
  const [v, setV] = useState(String(value))
  useEffect(() => setV(String(value)), [value])
  return (
    <div className="stat">
      <div className="muted" title={hint}>{label}{hint && <span className="help" title={hint}> ⓘ</span>}</div>
      <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
        <input type="number" step={step} value={v} onChange={(e) => setV(e.target.value)}
               style={{ width: 110 }} />
        <button onClick={() => onSave(Number(v))} disabled={Number(v) === value}>저장</button>
      </div>
    </div>
  )
}

/** 다음 적립 미리보기: 지금 실행하면 무슨 주문이 나갈지 / 왜 막히는지. */
function NextBuyCard({ preview, dryRun, onRun, busy }: {
  preview: BotPreview | null; dryRun: boolean; onRun: () => void; busy: boolean
}) {
  if (!preview) return null

  if (!preview.hasTarget) {
    return (
      <section className="card nextbuy">
        <h2>다음 적립 미리보기</h2>
        <p className="muted">{preview.reason ?? 'ETF와 목표비중을 추가하세요.'}</p>
      </section>
    )
  }

  const isMarket = preview.action === 'MARKET_BUY'
  const ok = preview.willTrade
  return (
    <section className="card nextbuy">
      <div className="card-head">
        <h2>다음 적립 미리보기</h2>
        <span className={`pill ${ok ? 'ok' : 'block'}`}>
          {ok ? (dryRun ? '🟢 적립 가능 (모의)' : '🟢 적립 실행됨') : '🔴 지금은 적립 안 함'}
        </span>
      </div>

      <div className="nextbuy-main">
        <div>
          <div className="nb-sym">{preview.name} <span className="muted">{preview.symbol}</span></div>
          <div className="nb-order">
            {isMarket ? '시장가' : `지정가 ${fmt(preview.price)}원`} · {fmt(preview.quantity)}주
          </div>
          {preview.decisionReason && <div className="muted" style={{ marginTop: 4 }}>{preview.decisionReason}</div>}
        </div>
        <div className="nb-cost">
          <div className="muted">예상 비용</div>
          <div className="big">{fmt(preview.estCost)}원</div>
          {preview.cashBuyingPower != null && (
            <div className="muted" style={{ fontSize: 12 }}>매수가능 {fmt(preview.cashBuyingPower)}원</div>
          )}
        </div>
      </div>

      {!ok && preview.blockReason && (
        <p className="muted" style={{ marginTop: 8 }}>지금 실행 시: <b style={{ color: 'var(--txt)' }}>{preview.blockReason}</b></p>
      )}
      {preview.warnings?.map((w, i) => (
        <p key={i} className="err" style={{ marginTop: 6 }}>⚠ {w}</p>
      ))}

      <div style={{ marginTop: 12 }}>
        <button onClick={onRun} disabled={busy}
                title="포트폴리오에서 목표비중 대비 가장 부족한 ETF를 1주 적립합니다">
          지금 1회 적립
        </button>
      </div>
    </section>
  )
}
