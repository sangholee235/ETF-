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
  target?: number   // 워터폴: 목표 금액(원)
}

export interface WaterfallStatus {
  symbol: string
  name: string
  investedKrw: number
  targetKrw: number
  fillPct: number               // 0~1
  status: 'done' | 'active' | 'wait'
}

export interface BotConfig {
  symbol: string
  symbol_name: string
  portfolio_mode: boolean
  portfolio: PortfolioItem[]
  fill_mode: 'weight' | 'waterfall'
  wait_for_underweight: boolean
  quantity_per_buy: number
  buy_amount_krw: number
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

export interface PortfolioProgress {
  symbol: string
  name: string
  targetWeight: number   // 0~1
  currentWeight: number  // 0~1 (누적 투입 기준)
  investedKrw: number
}

export interface BotPreview {
  dryRun: boolean
  enabled: boolean
  dailyBudgetKrw: number
  progress: PortfolioProgress[]
  fillMode: 'weight' | 'waterfall'
  waterfall: WaterfallStatus[]
  hasTarget: boolean
  reason?: string                 // hasTarget=false 일 때
  symbol?: string
  name?: string
  action?: 'LIMIT_BUY' | 'MARKET_BUY' | 'SKIP'
  quantity?: number
  price?: number | null           // 지정가 (시장가면 null)
  lastPrice?: number | null        // 현재 시세 (살 수 없어도 표시)
  estCost?: number
  decisionReason?: string
  willTrade?: boolean
  blockReason?: string | null
  cashBuyingPower?: number | null
  warnings?: string[]
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
  order_id?: string | null
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

export interface RankItem {
  symbol: string
  name: string
  market: string | null
  lastPrice: number
  changePct: number | null
  volume: number | null
  value: number | null
  marketCap: number | null
  currency: string
}

export interface IndexSummary {
  symbol: string
  label: string
  proxy: string
  lastPrice: number | null
  changePct: number | null
  spark: number[]
}

export interface Order {
  orderId: string
  symbol: string
  side: 'BUY' | 'SELL'
  orderType: 'LIMIT' | 'MARKET'
  status: string
  price: string | null
  quantity: string
  currency: string
  orderedAt: string
  execution: { filledQuantity: string; averageFilledPrice: string | null }
}

export interface OrdersPage {
  orders: Order[]
  nextCursor: string | null
  hasNext: boolean
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
