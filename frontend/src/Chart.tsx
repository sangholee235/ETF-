import { useEffect, useRef, useState } from 'react'
import {
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  createChart,
  type CandlestickData,
  type HistogramData,
  type IChartApi,
  type ISeriesApi,
  type LineData,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts'
import { api } from './api'

type Interval = '1d' | '1m'

export default function Chart({ symbol, name, broker }: { symbol: string; name?: string; broker?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candleRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const maRef = useRef<ISeriesApi<'Line'> | null>(null)
  const volRef = useRef<ISeriesApi<'Histogram'> | null>(null)
  const [interval, setInterval] = useState<Interval>('1d')
  const [err, setErr] = useState('')

  useEffect(() => {
    if (!ref.current) return
    const chart = createChart(ref.current, {
      height: 360,
      width: ref.current.clientWidth,
      layout: { background: { color: 'transparent' }, textColor: '#b0b4ba', fontFamily: 'inherit' },
      grid: { vertLines: { color: '#232329' }, horzLines: { color: '#232329' } },
      rightPriceScale: { borderColor: '#2c2c34', scaleMargins: { top: 0.08, bottom: 0.26 } },
      timeScale: { borderColor: '#2c2c34', timeVisible: interval === '1m' },
      crosshair: { mode: 0 },
    })
    candleRef.current = chart.addSeries(CandlestickSeries, {
      upColor: '#ff5b5b', downColor: '#4d9fff',
      borderUpColor: '#ff5b5b', borderDownColor: '#4d9fff',
      wickUpColor: '#ff5b5b', wickDownColor: '#4d9fff',
    })
    maRef.current = chart.addSeries(LineSeries, {
      color: '#f5a623', lineWidth: 2, priceLineVisible: false, lastValueVisible: false,
    })
    volRef.current = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' }, priceScaleId: 'vol',
    })
    chart.priceScale('vol').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } })
    chartRef.current = chart

    // 너비만 반응형으로 갱신 (높이는 360 고정 → 피드백 루프 방지)
    const ro = new ResizeObserver(() => {
      if (ref.current) chart.applyOptions({ width: ref.current.clientWidth })
    })
    ro.observe(ref.current)
    return () => {
      ro.disconnect()
      chart.remove()
      chartRef.current = null
    }
  }, [interval])

  useEffect(() => {
    let alive = true
    setErr('')
    api
      .candles(symbol, interval, 150, broker)
      .then((page) => {
        if (!alive || !candleRef.current) return
        const sorted = [...page.candles].sort(
          (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime(),
        )
        const candles: CandlestickData[] = sorted.map((c) => ({
          time: toTime(c.timestamp, interval),
          open: Number(c.openPrice), high: Number(c.highPrice),
          low: Number(c.lowPrice), close: Number(c.closePrice),
        }))
        const vols: HistogramData[] = sorted.map((c) => ({
          time: toTime(c.timestamp, interval),
          value: Number(c.volume),
          color: Number(c.closePrice) >= Number(c.openPrice) ? 'rgba(255,91,91,0.4)' : 'rgba(77,159,255,0.4)',
        }))
        const ma: LineData[] = movingAverage(sorted.map((c) => Number(c.closePrice)), 20)
          .map((v, i) => (v == null ? null : { time: toTime(sorted[i].timestamp, interval), value: v }))
          .filter((x): x is LineData => x !== null)

        candleRef.current.setData(candles)
        volRef.current?.setData(vols)
        maRef.current?.setData(ma)
        chartRef.current?.timeScale().fitContent()
      })
      .catch((e) => alive && setErr(String(e instanceof Error ? e.message : e)))
    return () => {
      alive = false
    }
  }, [symbol, interval, broker])

  return (
    <section className="card chart-card">
      <div className="card-head">
        <h2>{name ?? symbol} 차트 <span className="muted" style={{ fontWeight: 400 }}>· MA20 · 거래량</span></h2>
        <div className="seg">
          <button className={interval === '1d' ? 'on' : ''} onClick={() => setInterval('1d')}>일</button>
          <button className={interval === '1m' ? 'on' : ''} onClick={() => setInterval('1m')}>분</button>
        </div>
      </div>
      {err && <p className="err">{err}</p>}
      <div ref={ref} className="chart-host" />
    </section>
  )
}

function movingAverage(values: number[], period: number): (number | null)[] {
  const out: (number | null)[] = []
  let sum = 0
  for (let i = 0; i < values.length; i++) {
    sum += values[i]
    if (i >= period) sum -= values[i - period]
    out.push(i >= period - 1 ? sum / period : null)
  }
  return out
}

function toTime(iso: string, interval: Interval): Time {
  if (interval === '1d') return iso.slice(0, 10) as Time
  return Math.floor(new Date(iso).getTime() / 1000) as UTCTimestamp
}
