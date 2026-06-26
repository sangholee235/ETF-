import type {
  Account,
  BacktestResult,
  BotConfig,
  BotLog,
  BotStatus,
  BuyingPower,
  CandlePage,
  EtfCatalogItem,
  SweepResult,
  Holdings,
  Orderbook,
  OrdersPage,
  IndexSummary,
  Price,
  Quote,
  RankItem,
  StockInfo,
} from './types'

/** 알려진 에러 코드를 사용자 친화 메시지로 매핑. */
function friendly(code?: string): string | undefined {
  const map: Record<string, string> = {
    'rate-limit-exceeded': '요청이 잠시 많아요. 곧 자동으로 다시 시도합니다.',
    'stock-not-found': '종목을 찾을 수 없어요. 코드를 확인하세요.',
    'invalid-request': '요청 형식이 올바르지 않아요.',
    'account-not-found': '계좌를 찾을 수 없어요.',
    'insufficient-data': '백테스트할 과거 데이터가 부족해요.',
  }
  return code ? map[code] : undefined
}

async function get<T>(path: string): Promise<T> {
  return req<T>('GET', path)
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    let msg = res.statusText
    try {
      const detail = (await res.json()).detail
      if (typeof detail === 'string') msg = detail
      else if (detail && typeof detail === 'object') {
        const d = detail as { code?: string; message?: string }
        msg = friendly(d.code) ?? d.message ?? JSON.stringify(detail)
      }
    } catch {
      /* keep statusText */
    }
    throw new Error(msg)
  }
  return res.json() as Promise<T>
}

export const api = {
  accounts: () => get<Account[]>('/api/account/accounts'),
  prices: (symbols: string) => get<Price[]>(`/api/market/prices?symbols=${encodeURIComponent(symbols)}`),
  stocks: (symbols: string) => get<StockInfo[]>(`/api/market/stocks?symbols=${encodeURIComponent(symbols)}`),
  orderbook: (symbol: string) => get<Orderbook>(`/api/market/orderbook?symbol=${symbol}`),
  candles: (symbol: string, interval: string, count = 100) =>
    get<CandlePage>(`/api/market/candles?symbol=${symbol}&interval=${interval}&count=${count}`),
  exchangeRate: () => get<{ rate: string }>('/api/market/exchange-rate?base=USD&quote=KRW'),
  ranking: () => get<RankItem[]>('/api/market/ranking'),
  marketSummary: () => get<IndexSummary[]>('/api/market/market-summary'),
  holdings: () => get<Holdings>('/api/account/holdings'),
  openOrders: () => get<OrdersPage>('/api/orders?status=OPEN'),
  buyingPower: (currency: string) => get<BuyingPower>(`/api/account/buying-power?currency=${currency}`),

  // --- 적립봇 ---
  botStatus: () => get<BotStatus>('/api/bot/status'),
  botCatalog: () => get<EtfCatalogItem[]>('/api/bot/catalog'),
  botRun: () => req<Record<string, unknown>>('POST', '/api/bot/run'),
  botPatchConfig: (patch: Partial<BotConfig>) =>
    req<BotConfig>('PATCH', '/api/bot/config', patch),
  botLogs: (limit = 200) => get<BotLog[]>(`/api/bot/logs?limit=${limit}`),
  botBacktest: (symbol: string, days: number, discountPct: number, fallback: number, commissionPct = 0) =>
    get<BacktestResult>(
      `/api/bot/backtest?symbol=${symbol}&days=${days}&discount_pct=${discountPct}&fallback_after_misses=${fallback}&commission_pct=${commissionPct}`,
    ),
  botSweep: (symbol: string, days: number, commissionPct = 0) =>
    get<SweepResult>(`/api/bot/backtest/sweep?symbol=${symbol}&days=${days}&commission_pct=${commissionPct}`),
}

/** 대시보드용 통합 조회: 시세 + 종목명 + 호가1단계 묶음 */
export async function loadQuotes(symbolsCsv: string): Promise<Quote[]> {
  const symbols = symbolsCsv.split(',').map((s) => s.trim()).filter(Boolean)
  if (!symbols.length) return []

  // 현재가는 필수, 종목정보(이름)는 브로커에 따라 없을 수 있으니 실패해도 진행
  const [prices, stocks] = await Promise.all([
    api.prices(symbolsCsv),
    api.stocks(symbolsCsv).catch(() => [] as StockInfo[]),
  ])
  const priceMap = new Map(prices.map((p) => [p.symbol, p]))
  const stockMap = new Map(stocks.map((s) => [s.symbol, s]))

  const obs = await Promise.all(
    symbols.map((s) => api.orderbook(s).catch(() => null)),
  )

  return symbols.map((sym, i) => {
    const p = priceMap.get(sym)
    const s = stockMap.get(sym)
    const ob = obs[i]
    return {
      symbol: sym,
      name: s?.name ?? sym,
      market: s?.market,
      lastPrice: p?.lastPrice ?? null,
      currency: p?.currency ?? null,
      timestamp: p?.timestamp ?? null,
      ask1: ob?.asks?.[0] ?? null,
      bid1: ob?.bids?.[0] ?? null,
    }
  })
}
