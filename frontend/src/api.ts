import type {
  Account,
  BuyingPower,
  Holdings,
  Orderbook,
  Price,
  Quote,
  StockInfo,
} from './types'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) {
    let detail: unknown
    try {
      detail = (await res.json()).detail
    } catch {
      detail = res.statusText
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return res.json() as Promise<T>
}

export const api = {
  accounts: () => get<Account[]>('/api/account/accounts'),
  prices: (symbols: string) => get<Price[]>(`/api/market/prices?symbols=${encodeURIComponent(symbols)}`),
  stocks: (symbols: string) => get<StockInfo[]>(`/api/market/stocks?symbols=${encodeURIComponent(symbols)}`),
  orderbook: (symbol: string) => get<Orderbook>(`/api/market/orderbook?symbol=${symbol}`),
  holdings: () => get<Holdings>('/api/account/holdings'),
  buyingPower: (currency: string) => get<BuyingPower>(`/api/account/buying-power?currency=${currency}`),
}

/** 대시보드용 통합 조회: 시세 + 종목명 + 호가1단계 묶음 */
export async function loadQuotes(symbolsCsv: string): Promise<Quote[]> {
  const symbols = symbolsCsv.split(',').map((s) => s.trim()).filter(Boolean)
  if (!symbols.length) return []

  const [prices, stocks] = await Promise.all([api.prices(symbolsCsv), api.stocks(symbolsCsv)])
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
