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
