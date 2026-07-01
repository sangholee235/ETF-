import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import HoldingsDonut from './HoldingsDonut'
import PortfolioPanel from './PortfolioPanel'
import type { Account, BotPreview, BotStatus, BuyingPower, EtfCatalogItem, Holdings, Order } from './types'

const fmt = (v: string | number | null | undefined) =>
  v == null ? '-' : Number(v).toLocaleString()
/** ISO 시각 → 'MM-DD HH:MM' (브로커 공통). 파싱 실패 시 원본/대시. */
const fmtTime = (v: string | null | undefined) => {
  if (!v) return '-'
  const d = new Date(v)
  if (isNaN(d.getTime())) return v
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}
const pct = (v: string | null | undefined) =>
  v == null ? '-' : (Number(v) * 100).toFixed(2) + '%'
const sign = (v: string | null | undefined) =>
  v == null ? '' : Number(v) >= 0 ? 'up' : 'down'

const LABEL: Record<string, string> = { toss: '토스증권', kiwoom: '키움증권' }

/** ETF 자동 적립 메인. ①보유 비중 → ②목표 비중 → ③전략 상태 → ④실행 기록 흐름. */
export default function AutoPage() {
  const [brokers, setBrokers] = useState<string[]>([])
  const [broker, setBroker] = useState('')

  useEffect(() => {
    api.brokers()
      .then((r) => { setBrokers(r.brokers); setBroker((p) => p || r.default || r.brokers[0] || '') })
      .catch(() => {})
  }, [])

  if (!broker) return <LoadingSkeleton />

  return (
    <>
      <section className="card span2 broker-bar">
        {brokers.map((b) => (
          <button key={b} onClick={() => setBroker(b)} className={`broker-btn ${broker === b ? 'on' : ''}`}>
            {LABEL[b] ?? b}
          </button>
        ))}
      </section>
      <BrokerView key={broker} broker={broker} />
    </>
  )
}

function BrokerView({ broker }: { broker: string }) {
  const [status, setStatus] = useState<BotStatus | null>(null)
  const [holdings, setHoldings] = useState<Holdings | null>(null)
  const [preview, setPreview] = useState<BotPreview | null>(null)
  const [catalog, setCatalog] = useState<EtfCatalogItem[]>([])
  const [account, setAccount] = useState<Account | null>(null)
  const [bp, setBp] = useState<BuyingPower | null>(null)
  const [sched, setSched] = useState<Awaited<ReturnType<typeof api.botScheduler>> | null>(null)
  const [rt, setRt] = useState<Awaited<ReturnType<typeof api.botRealtime>> | null>(null)
  const [openOrders, setOpenOrders] = useState<Order[]>([])
  const [trades, setTrades] = useState<Order[]>([])
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try {
      const [s, h, p, c, a, b, sc, oo, tr] = await Promise.all([
        api.botStatus(broker),
        api.holdings(broker).catch(() => null),
        api.botPreview(broker).catch(() => null),
        api.botCatalog(broker),
        api.accounts(broker).then((x) => x[0] ?? null).catch(() => null),
        api.buyingPower('KRW', broker).catch(() => null),
        api.botScheduler().catch(() => null),
        api.openOrders(broker).catch(() => null),
        api.closedOrders(broker).catch(() => null),
      ])
      setStatus(s); setHoldings(h); setPreview(p); setCatalog(c); setAccount(a); setBp(b); setSched(sc)
      setOpenOrders(oo?.orders ?? [])
      setTrades(tr?.orders ?? [])
    } catch (e) {
      setMsg(String(e instanceof Error ? e.message : e))
    }
  }, [broker])

  useEffect(() => {
    load()
    const t = setInterval(() => {
      api.botScheduler().then(setSched).catch(() => {})
      api.botRealtime().then(setRt).catch(() => {})
    }, 15000)
    api.botRealtime().then(setRt).catch(() => {})
    return () => clearInterval(t)
  }, [load])

  // 실시간 체결통보(SSE): 체결 들어오면 즉시 화면 갱신 + 토스트
  useEffect(() => {
    const es = new EventSource('/api/bot/stream')
    es.addEventListener('fill', (e) => {
      try {
        const d = JSON.parse((e as MessageEvent).data) as {
          orderStatus?: string; name?: string; symbol?: string; filledQty?: string; filledPrice?: string
        }
        if (d.orderStatus && d.orderStatus.includes('체결')) {
          const px = d.filledPrice ? ` @${Number(d.filledPrice).toLocaleString()}` : ''
          setMsg(`🔔 체결: ${d.name ?? d.symbol ?? ''} ${d.filledQty ?? ''}주${px}`)
        }
        load()
      } catch { /* ignore */ }
    })
    return () => es.close()
  }, [load])

  async function patch(p: Parameters<typeof api.botPatchConfig>[0]) {
    setBusy(true); setMsg('')
    try { await api.botPatchConfig(p, broker); await load() }
    catch (e) { setMsg(String(e instanceof Error ? e.message : e)) }
    finally { setBusy(false) }
  }
  async function cancelOrder(orderId: string, label: string) {
    if (!confirm(`${label} 주문을 취소할까요?`)) return
    setBusy(true); setMsg('취소 중...')
    try {
      await api.cancelOrder(orderId, broker)
      setMsg(`취소 요청됨: ${orderId}`); await load()
    } catch (e) { setMsg(String(e instanceof Error ? e.message : e)) }
    finally { setBusy(false) }
  }
  async function runTick() {
    setBusy(true); setMsg('실행 중...')
    try {
      const r = await api.botRun(broker)
      const d = (r.decision ?? {}) as { action?: string; reason?: string }
      setMsg(`결과: ${d.action} — ${d.reason}`); await load()
    } catch (e) { setMsg(String(e instanceof Error ? e.message : e)) }
    finally { setBusy(false) }
  }

  const cfg = status?.config
  const st = status?.state
  if (!cfg || !st) return <LoadingSkeleton msg={msg} />

  // 실행 기록 '체결' 보강: 로그의 filled 가 아직 null 이어도 거래내역에 체결로 있으면 ✅
  const fillByOrderId = new Map<string, boolean>()
  for (const t of trades) {
    if (t.orderId) fillByOrderId.set(t.orderId, t.status === 'FILLED' || t.status === 'PARTIAL_FILLED')
  }
  const logFilled = (lg: typeof st.logs[number]): boolean | null => {
    if (lg.filled != null) return lg.filled
    const oid = lg.order_id
    return oid && fillByOrderId.has(oid) ? fillByOrderId.get(oid)! : null
  }


  return (
    <>
      {/* ───────── 1. 지금 내 자산 ───────── */}
      <StepHead n={1} title="지금 내 자산" sub="무엇을 · 얼마 비중으로 갖고 있나" />
      <section className="card span2 hero">
        <div className="hero-main">
          <div className="muted">평가자산 (KRW)</div>
          <div className="hero-amount">{fmt(holdings?.marketValue.amount.krw)}<span className="won">원</span></div>
          {holdings && (
            <div className={`hero-pl ${sign(holdings.profitLoss.amount.krw)}`}>
              {Number(holdings.profitLoss.amount.krw) >= 0 ? '▲' : '▼'} {fmt(Math.abs(Number(holdings.profitLoss.amount.krw)))}원 ({pct(holdings.profitLoss.rate)})
            </div>
          )}
        </div>
        <div className="hero-sub">
          <Stat label="계좌번호" value={account?.accountNo ?? '-'} />
          <Stat label="매수가능(KRW)" value={fmt(bp?.cashBuyingPower) + '원'} />
          <Stat label="보유 종목수" value={(holdings?.items.length ?? 0) + '개'} />
        </div>
      </section>
      <HoldingsDonut holdings={holdings} />
      <HoldingsTable holdings={holdings} />

      {/* ───────── 2. 내 전략 (목표 비중) ───────── */}
      <StepHead n={2} title="내 전략 — 목표 비중" sub="어느 비중으로 무엇을 살지 정해서 저장" />
      <PortfolioPanel cfg={cfg} catalog={catalog} onPatch={patch} busy={busy}
                      progress={preview?.progress} waterfall={preview?.waterfall} nextSymbol={preview?.symbol} />

      {/* ───────── 3. 전략 상태 ───────── */}
      <StepHead n={3} title="전략 상태" sub="지금 자동으로 돌아가고 있나" />
      <section className="card span2 strat">
        <div className="strat-row">
          <div className={`strat-led ${cfg.schedule_enabled && cfg.enabled ? 'on' : 'off'}`}>
            <span className="led-dot" />
            <div>
              <div className="led-title">
                {cfg.enabled
                  ? cfg.schedule_enabled ? '자동 적립 작동 중' : '자동 OFF (수동 적립만)'
                  : '봇 정지됨 (킬스위치)'}
              </div>
              <div className="muted">
                {cfg.schedule_enabled
                  ? `매 평일 ${cfg.schedule_time} 실행 · ${cfg.dry_run ? 'DRY_RUN(모의)' : 'LIVE(실주문)'}`
                  : `버튼으로만 적립 · ${cfg.dry_run ? 'DRY_RUN(모의)' : 'LIVE(실주문)'}`}
              </div>
              <div className="sched-hb">
                {sched?.alive
                  ? <span className="up">● 스케줄러 동작 중{sched.secondsSinceTick != null ? ` · ${sched.secondsSinceTick}초 전 점검` : ''}</span>
                  : <span className="down">● 스케줄러 응답 없음 (백엔드 확인)</span>}
              </div>
              {rt?.broker === 'kiwoom' && (
                <div className="sched-hb">
                  {rt.connected
                    ? <span className="up">● 실시간 체결통보 연결됨</span>
                    : <span className="muted">○ 실시간 체결통보 대기{rt.lastError ? ` (${rt.lastError})` : ''}</span>}
                </div>
              )}
            </div>
          </div>
          <div className="strat-ctrl">
            <label className="muted sched-time">
              실행 시각
              <input type="time" defaultValue={cfg.schedule_time}
                     onBlur={(e) => e.target.value !== cfg.schedule_time && patch({ schedule_time: e.target.value })} />
            </label>
            <button onClick={() => patch({ schedule_enabled: !cfg.schedule_enabled })} disabled={busy}
                    style={{ background: cfg.schedule_enabled ? '#2b8a3e' : '#3a3a44' }}>
              {cfg.schedule_enabled ? '자동 ON' : '자동 OFF'}
            </button>
            <button onClick={() => { if (cfg.dry_run && !confirm('LIVE 전환 시 실제 돈으로 주문이 나갑니다. 계속할까요?')) return; patch({ dry_run: !cfg.dry_run }) }}
                    disabled={busy} style={{ background: cfg.dry_run ? '#e8590c' : '#2b8a3e' }}>
              {cfg.dry_run ? 'LIVE 전환' : 'DRY 전환'}
            </button>
            <button onClick={() => patch({ enabled: !cfg.enabled })} disabled={busy}
                    style={{ background: cfg.enabled ? '#c92a2a' : '#3182f6' }}>
              {cfg.enabled ? '봇 정지' : '봇 가동'}
            </button>
          </div>
        </div>
        <div className="strat-stats">
          <Stat label="누적 투입(추정)" value={fmt(st.totalInvestedKrw) + '원'} />
          <Stat label="보유 수량(추정)" value={fmt(st.totalFilledQty) + '주'} />
          <Stat label="연속 미체결" value={`${st.consecutiveMisses} / ${cfg.fallback_after_misses}일`} />
        </div>
        {msg && <p className="muted" style={{ marginTop: 8 }}>{msg}</p>}
      </section>

      <NextBuy preview={preview} dryRun={cfg.dry_run} onRun={runTick} busy={busy} />

      <ManualOrder broker={broker} defaultSymbol={preview?.symbol ?? cfg.portfolio?.[0]?.symbol ?? ''}
                   tick={cfg.tick_size || 5} dryRun={cfg.dry_run} onDone={load} />

      <section className="card span2">
        <h2>대기 중 주문 (미체결) <span className="muted" style={{ fontWeight: 400 }}>· 여기 있으면 대기, 사라지면 체결/취소</span></h2>
        {openOrders.length === 0 ? (
          <p className="muted">대기 중인 주문 없음</p>
        ) : (
          <div className="table-scroll">
            <table>
              <thead><tr><th>종목</th><th>구분</th><th>유형</th><th>가격</th><th>수량</th><th>체결</th><th>상태</th><th></th></tr></thead>
              <tbody>
                {openOrders.map((o) => {
                  const nm = (o as Order & { name?: string }).name ?? o.symbol
                  return (
                  <tr key={o.orderId}>
                    <td>{nm} <span className="muted">{o.symbol}</span></td>
                    <td className={o.side === 'BUY' ? 'up' : 'down'}>{o.side === 'BUY' ? '매수' : '매도'}</td>
                    <td>{o.orderType === 'LIMIT' ? '지정가' : '시장가'}</td>
                    <td>{o.price ? Number(o.price).toLocaleString() : '-'}</td>
                    <td>{o.quantity}</td>
                    <td>{o.execution.filledQuantity}/{o.quantity}</td>
                    <td className="muted">{o.status}</td>
                    <td>
                      <button className="ghost" onClick={() => cancelOrder(o.orderId, `${nm} ${o.orderType === 'LIMIT' ? '지정가' : '시장가'} ${o.quantity}주`)}
                              disabled={busy} style={{ color: 'var(--down, #f04452)', padding: '4px 10px' }}>
                        취소
                      </button>
                    </td>
                  </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ───────── 4. 실행 기록 ───────── */}
      <StepHead n={4} title="실행 기록" sub="언제 · 무엇을 적립했나" />
      <section className="card span2">
        <div className="table-scroll">
          <table>
            <thead><tr><th>시각</th><th>모드</th><th>종목</th><th>액션</th><th>가격</th><th>체결</th><th>사유</th></tr></thead>
            <tbody>
              {st.logs.length === 0 ? (
                <tr><td colSpan={7} className="muted">아직 실행 기록 없음 — "지금 1회 적립"으로 시작</td></tr>
              ) : (
                [...st.logs].reverse().map((lg, i) => {
                  const f = logFilled(lg)
                  return (
                  <tr key={i}>
                    <td className="muted">{lg.ts.slice(0, 16).replace('T', ' ')}</td>
                    <td><span style={{ color: lg.mode === 'LIVE' ? 'var(--up)' : 'var(--muted)' }}>{lg.mode}</span></td>
                    <td>{lg.symbol ?? '-'}</td>
                    <td>{actionKo(lg.action)}</td>
                    <td>{fmt(lg.price)}</td>
                    <td>{f == null ? '-' : f ? '✅' : '❌'}</td>
                    <td className="muted">{lg.reason}</td>
                  </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card span2">
        <h2>거래내역 (실제 체결) <span className="muted" style={{ fontWeight: 400 }}>· 증권사 체결 기록</span></h2>
        {trades.length === 0 ? (
          <p className="muted">체결된 거래 없음</p>
        ) : (
          <div className="table-scroll">
            <table>
              <thead><tr><th>시각</th><th>종목</th><th>구분</th><th>유형</th><th>체결가</th><th>수량</th><th>체결금액</th><th>상태</th></tr></thead>
              <tbody>
                {trades.map((o) => {
                  const ex = o.execution as Order['execution'] & { filledAmount?: string }
                  return (
                    <tr key={o.orderId}>
                      <td className="muted">{fmtTime((o as Order & { orderedAt?: string }).orderedAt)}</td>
                      <td>{(o as Order & { name?: string }).name ?? o.symbol} <span className="muted">{o.symbol}</span></td>
                      <td className={o.side === 'BUY' ? 'up' : 'down'}>{o.side === 'BUY' ? '매수' : '매도'}</td>
                      <td>{o.orderType === 'LIMIT' ? '지정가' : '시장가'}</td>
                      <td>{ex.averageFilledPrice ? Number(ex.averageFilledPrice).toLocaleString() : '-'}</td>
                      <td>{ex.filledQuantity}</td>
                      <td>{ex.filledAmount ? Number(ex.filledAmount).toLocaleString() : '-'}</td>
                      <td className="muted">{o.status === 'FILLED' ? '체결' : o.status === 'PARTIAL_FILLED' ? '일부체결' : o.status}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* 세부 설정 (접기) */}
      <DetailSettings cfg={cfg} onPatch={patch} />
    </>
  )
}

/** 보유 종목별 평가·손익·수익률 표. */
function HoldingsTable({ holdings }: { holdings: Holdings | null }) {
  const items = holdings?.items ?? []
  return (
    <section className="card span2">
      <h2>보유 종목 수익률 <span className="muted" style={{ fontWeight: 400 }}>· 종목별 평가손익</span></h2>
      {items.length === 0 ? (
        <p className="muted">보유 종목 없음</p>
      ) : (
        <div className="table-scroll">
          <table>
            <thead><tr><th>종목</th><th>수량</th><th>평균가</th><th>현재가</th><th>평가금액</th><th>손익</th><th>수익률</th></tr></thead>
            <tbody>
              {items.map((it) => {
                const pl = it.profitLoss?.amount
                const s = sign(pl)
                return (
                  <tr key={it.symbol}>
                    <td style={{ textAlign: 'left' }}>{it.name} <span className="muted">{it.symbol}</span></td>
                    <td>{fmt(it.quantity)}</td>
                    <td>{fmt(it.averagePurchasePrice)}</td>
                    <td>{fmt(it.lastPrice)}</td>
                    <td>{fmt(it.marketValue?.amount)}</td>
                    <td className={s}>{pl != null && Number(pl) >= 0 ? '▲' : '▼'} {fmt(pl != null ? Math.abs(Number(pl)) : null)}</td>
                    <td className={s}>{pct(it.profitLoss?.rate)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

function Skel({ w, h = 16, r = 6 }: { w: number | string; h?: number; r?: number }) {
  return <span className="skel" style={{ width: w, height: h, borderRadius: r }} />
}

/** 첫 로딩 시 실제 화면 골격(자산 히어로 → 목표 비중 → 전략 상태)을 스켈레톤으로 표시. */
function LoadingSkeleton({ msg }: { msg?: string }) {
  return (
    <>
      <section className="card span2 hero">
        <div className="hero-main">
          <Skel w={90} h={13} />
          <div className="hero-amount" style={{ marginTop: 8 }}><Skel w={180} h={30} /></div>
          <div style={{ marginTop: 8 }}><Skel w={140} h={15} /></div>
        </div>
        <div className="hero-sub">
          {[0, 1, 2].map((i) => (
            <div className="stat" key={i}><Skel w={64} h={12} /><div style={{ marginTop: 6 }}><Skel w={88} h={18} /></div></div>
          ))}
        </div>
      </section>
      <section className="card"><Skel w="60%" h={14} /><div style={{ marginTop: 16 }}><Skel w={180} h={180} r={90} /></div></section>
      <section className="card span2">
        <Skel w={140} h={18} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 16 }}>
          {[0, 1, 2].map((i) => <Skel key={i} w="100%" h={44} r={12} />)}
        </div>
      </section>
      <section className="card span2"><Skel w={120} h={18} /><div style={{ marginTop: 14 }}><Skel w="100%" h={64} r={12} /></div></section>
      {msg && <section className="card span2"><span className="err">{msg}</span></section>}
    </>
  )
}

function actionKo(a: string): string {
  if (a === 'LIMIT_BUY') return '지정가 매수'
  if (a === 'MARKET_BUY') return '시장가 매수'
  if (a === 'SKIP') return '건너뜀'
  return a
}

function StepHead({ n, title, sub }: { n: number; title: string; sub: string }) {
  return (
    <div className="span2 step-head">
      <span className="step-no">{n}</span>
      <div><div className="step-title">{title}</div><div className="muted step-sub">{sub}</div></div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return <div className="stat"><div className="muted">{label}</div><div className="big">{value}</div></div>
}

function NextBuy({ preview, dryRun, onRun, busy }: {
  preview: BotPreview | null; dryRun: boolean; onRun: () => void; busy: boolean
}) {
  if (!preview) return null
  if (!preview.hasTarget) {
    return <section className="card span2 nextbuy"><h2>다음 적립</h2><p className="muted">{preview.reason ?? '위에서 ETF와 목표비중을 추가하세요.'}</p></section>
  }
  const isMarket = preview.action === 'MARKET_BUY'
  const ok = preview.willTrade
  return (
    <section className="card span2 nextbuy">
      <div className="card-head">
        <h2>다음 적립 미리보기</h2>
        <span className={`pill ${ok ? 'ok' : 'block'}`}>
          {ok ? (dryRun ? '🟢 적립 가능(모의)' : '🟢 적립 실행') : '🔴 지금은 적립 안 함'}
        </span>
      </div>
      <div className="nextbuy-main">
        <div>
          <div className="nb-sym">{preview.name} <span className="muted">{preview.symbol}</span></div>
          {preview.lastPrice != null && (
            <div className="muted" style={{ marginTop: 2 }}>현재가 {fmt(preview.lastPrice)}원</div>
          )}
          {preview.action === 'SKIP'
            ? <div className="nb-order muted">지금은 적립 안 함</div>
            : <div className="nb-order">{isMarket ? '시장가' : `지정가 ${fmt(preview.price)}원`} · {fmt(preview.quantity)}주</div>}
          {preview.decisionReason && <div className="muted" style={{ marginTop: 4 }}>{preview.decisionReason}</div>}
        </div>
        <div className="nb-cost">
          <div className="muted">{preview.estCost != null ? '예상 비용' : '1주 가격'}</div>
          <div className="big">{fmt(preview.estCost ?? preview.lastPrice)}원</div>
          {preview.cashBuyingPower != null && <div className="muted" style={{ fontSize: 12 }}>매수가능 {fmt(preview.cashBuyingPower)}원</div>}
        </div>
      </div>
      {!ok && preview.blockReason && <p className="muted" style={{ marginTop: 8 }}>지금 실행 시: <b style={{ color: 'var(--txt)' }}>{preview.blockReason}</b></p>}
      {preview.warnings?.map((w, i) => <p key={i} className="err" style={{ marginTop: 6 }}>⚠ {w}</p>)}
      <div style={{ marginTop: 12 }}>
        <button onClick={onRun} disabled={busy}>지금 1회 적립</button>
      </div>
    </section>
  )
}

function roundTick(p: number, tick: number): number {
  return Math.floor(p / tick) * tick
}

/** 수동 매수 — 가격을 틱 단위로 조절해 직접 주문. 현재가 실시간(3초 폴링) 표시. */
function ManualOrder({ broker, defaultSymbol, tick, dryRun, onDone }: {
  broker: string; defaultSymbol: string; tick: number; dryRun: boolean; onDone: () => void
}) {
  const [symbol, setSymbol] = useState(defaultSymbol)
  const [qty, setQty] = useState(1)
  const [price, setPrice] = useState<number | null>(null)
  const [isMarket, setIsMarket] = useState(false)
  const [live, setLive] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')

  useEffect(() => { setSymbol(defaultSymbol) }, [defaultSymbol])

  // 실시간 현재가 (3초 폴링). 가격 비어있으면 최초 1회 현재가(틱 반올림)로 채움.
  useEffect(() => {
    if (!symbol) { setLive(null); return }
    let alive = true
    const tickFn = () => api.prices(symbol, broker).then((ps) => {
      if (!alive) return
      const n = ps[0]?.lastPrice != null ? Number(ps[0].lastPrice) : null
      setLive(n)
      setPrice((cur) => (cur == null && n != null ? roundTick(n, tick) : cur))
    }).catch(() => {})
    tickFn()
    const t = setInterval(tickFn, 3000)
    return () => { alive = false; clearInterval(t) }
  }, [symbol, broker, tick])

  const step = (d: number) => setPrice((p) => Math.max(tick, roundTick((p ?? live ?? tick) + d * tick, tick)))

  async function buy() {
    if (!symbol) { setMsg('종목코드를 입력하세요'); return }
    if (!isMarket && (!price || price <= 0)) { setMsg('지정가를 입력하세요'); return }
    const label = `${symbol} ${isMarket ? '시장가' : `지정가 ${price!.toLocaleString()}원`} ${qty}주`
    const warn = dryRun ? '' : '⚠️ 실제 주문(LIVE)입니다.\n'
    if (!confirm(`${warn}${label} 매수할까요?`)) return
    setBusy(true); setMsg('')
    try {
      const r = await api.placeBuy(
        { symbol, quantity: qty, price: isMarket ? null : price, orderType: isMarket ? 'MARKET' : 'LIMIT' }, broker)
      setMsg(`주문 접수됨: ${r.orderId ?? '완료'}`)
      onDone()
    } catch (e) { setMsg(String(e instanceof Error ? e.message : e)) }
    finally { setBusy(false) }
  }

  return (
    <section className="card span2">
      <h2>수동 매수 <span className="muted" style={{ fontWeight: 400 }}>· 가격 직접 지정 (틱 {tick}원 단위)</span></h2>
      <div className="row" style={{ gap: 10, alignItems: 'flex-end', flexWrap: 'wrap' }}>
        <label className="stat"><div className="muted">종목코드</div>
          <input value={symbol} onChange={(e) => setSymbol(e.target.value.trim())} style={{ width: 100 }} /></label>
        <label className="stat"><div className="muted">수량(주)</div>
          <input type="number" min={1} value={qty} onChange={(e) => setQty(Math.max(1, Number(e.target.value) || 1))} style={{ width: 70 }} /></label>
        <div className="stat"><div className="muted">현재가 {live != null ? '● 실시간' : ''}</div>
          <div className="big">{live != null ? live.toLocaleString() : '-'}원</div></div>
        {!isMarket && (
          <div className="stat"><div className="muted">지정가</div>
            <div style={{ display: 'flex', gap: 4, alignItems: 'center', marginTop: 4 }}>
              <button onClick={() => step(-1)} disabled={busy}>−{tick}</button>
              <input type="number" step={tick} value={price ?? ''}
                     onChange={(e) => setPrice(e.target.value ? Number(e.target.value) : null)} style={{ width: 90 }} />
              <button onClick={() => step(1)} disabled={busy}>＋{tick}</button>
              <button className="ghost" onClick={() => live != null && setPrice(roundTick(live, tick))} disabled={busy}>현재가</button>
            </div></div>
        )}
        <div className="seg" style={{ marginBottom: 2 }}>
          <button className={!isMarket ? 'on' : ''} onClick={() => setIsMarket(false)}>지정가</button>
          <button className={isMarket ? 'on' : ''} onClick={() => setIsMarket(true)}>시장가</button>
        </div>
        <button onClick={buy} disabled={busy} style={{ background: 'var(--up, #f04452)', color: '#fff' }}>매수</button>
      </div>
      {!isMarket && price != null && qty > 0 && (
        <p className="muted" style={{ marginTop: 8 }}>예상 금액: <b style={{ color: 'var(--txt)' }}>{(price * qty).toLocaleString()}원</b></p>
      )}
      {msg && <p className="muted" style={{ marginTop: 6 }}>{msg}</p>}
    </section>
  )
}

function DetailSettings({ cfg, onPatch }: {
  cfg: BotStatus['config']; onPatch: (p: Parameters<typeof api.botPatchConfig>[0]) => void
}) {
  const [open, setOpen] = useState(false)
  return (
    <section className="card span2">
      <button className="ghost" onClick={() => setOpen(!open)} style={{ padding: 0, color: 'var(--txt2)' }}>
        {open ? '▾' : '▸'} 세부 설정 (하루 적립 금액 · 지정가 할인 · 시장가 전환)
      </button>
      {open && (
        <>
          <p className="muted" style={{ marginTop: 12, marginBottom: 4 }}>
            <b style={{ color: 'var(--txt)' }}>하루 적립 금액</b> 안에서 부족한 ETF를 살 수 있는 만큼 매수해요. (예: 10만원이면 그 ETF를 10만원 안에서)
          </p>
          <div className="row" style={{ marginTop: 8 }}>
            <Num label="하루 적립 금액(원)" value={cfg.daily_budget_krw} step={10000} onSave={(v) => onPatch({ daily_budget_krw: v })} />
            <Num label="지정가 할인(%)" value={cfg.discount_pct * 100} step={0.1} min={0} onSave={(v) => onPatch({ discount_pct: Math.max(0, v) / 100 })} />
            <Num label="시장가 전환(일)" value={cfg.fallback_after_misses} onSave={(v) => onPatch({ fallback_after_misses: v })} />
          </div>
        </>
      )}
    </section>
  )
}

function Num({ label, value, step = 1, min, onSave }: { label: string; value: number; step?: number; min?: number; onSave: (v: number) => void }) {
  const [v, setV] = useState(String(value))
  useEffect(() => setV(String(value)), [value])
  return (
    <div className="stat">
      <div className="muted">{label}</div>
      <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
        <input type="number" step={step} min={min} value={v} onChange={(e) => setV(e.target.value)} style={{ width: 110 }} />
        <button onClick={() => onSave(Number(v))} disabled={Number(v) === value}>저장</button>
      </div>
    </div>
  )
}
