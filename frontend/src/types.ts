export interface Account {
  accountNo: string
  accountSeq: number
  accountType: string
}

export interface Price {
  symbol: string
  timestamp: string | null
  lastPrice: string
  currency: string
}

export interface StockInfo {
  symbol: string
  name: string
  market: string
  status: string
}

export interface OrderbookEntry {
  price: string
  volume: string
}

export interface Orderbook {
  timestamp: string | null
  currency: string
  asks: OrderbookEntry[]
  bids: OrderbookEntry[]
}

export interface BuyingPower {
  currency: string
  cashBuyingPower: string
}

export interface HoldingsItem {
  symbol: string
  name: string
  currency: string
  quantity: string
  lastPrice: string
  averagePurchasePrice: string
  marketValue: { purchaseAmount: string; amount: string; amountAfterCost: string }
  profitLoss: { amount: string; rate: string; amountAfterCost: string; rateAfterCost: string }
}

export interface Holdings {
  marketValue: { amount: { krw: string; usd: string | null } }
  profitLoss: { amount: { krw: string; usd: string | null }; rate: string }
  items: HoldingsItem[]
}

export interface Candle {
  timestamp: string
  openPrice: string
  highPrice: string
  lowPrice: string
  closePrice: string
  volume: string
  currency: string
}

export interface CandlePage {
  candles: Candle[]
  nextBefore: string | null
}

export interface PortfolioItem {
  symbol: string
  name: string
  weight: number
}

export interface BotConfig {
  symbol: string
  symbol_name: string
  portfolio_mode: boolean
  portfolio: PortfolioItem[]
  quantity_per_buy: number
  discount_pct: number
  fallback_after_misses: number
  tick_size: number
  daily_budget_krw: number
  total_budget_krw: number
  require_market_open: boolean
  schedule_enabled: boolean
  schedule_time: string
  dry_run: boolean
  enabled: boolean
}

export interface BotLog {
  ts: string
  trade_date: string
  mode: string
  action: string
  reason: string
  symbol: string
  quantity: number
  price: number | null
  filled: boolean | null
}

export interface BotStatus {
  config: BotConfig
  state: {
    totalInvestedKrw: number
    totalFilledQty: number
    consecutiveMisses: number
    lastTradeDate: string | null
    logs: BotLog[]
  }
}

export interface BacktestLeg {
  shares: number
  invested: number
  avgPrice: number
  marketValue: number
  profit: number
  returnPct: number
  buys: number
  marketFallbacks?: number
  tradingDays?: number
}

export interface BacktestResult {
  symbol: string
  period: { from: string; to: string; days: number }
  params: { discountPct: number; fallbackAfterMisses: number; quantity: number }
  lastClose: number
  strategyLimit: BacktestLeg
  strategyDaily: BacktestLeg
  lowerAvgPrice: 'limit' | 'daily'
  series: { date: string; price: number; limitAvg: number | null; dailyAvg: number | null }[]
}

export interface SweepRow {
  discountPct: number
  fallback: number
  shares: number
  buys: number
  marketFallbacks: number
  avgPrice: number
  returnPct: number
}

export interface SweepResult {
  symbol: string
  period: { from: string; to: string; days: number }
  lastClose: number
  baselineDaily: { avgPrice: number; returnPct: number }
  results: SweepRow[]
}

export interface EtfCatalogItem {
  symbol: string
  name: string
  category: string
  tax: 'exempt' | 'taxed'
  lastPrice: string | null
}

export interface Quote {
  symbol: string
  name: string
  market?: string
  lastPrice: string | null
  currency: string | null
  timestamp: string | null
  ask1: OrderbookEntry | null
  bid1: OrderbookEntry | null
}
