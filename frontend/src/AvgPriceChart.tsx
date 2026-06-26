import { useEffect, useRef } from 'react'
import { LineSeries, createChart, type IChartApi, type LineData, type Time } from 'lightweight-charts'
import type { BacktestResult } from './types'

/** 백테스트 평단/종가 추이 라인 차트. */
export default function AvgPriceChart({ series }: { series: BacktestResult['series'] }) {
  const ref = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)

  useEffect(() => {
    if (!ref.current) return
    const chart = createChart(ref.current, {
      height: 240,
      layout: { background: { color: 'transparent' }, textColor: '#b0b4ba', fontFamily: 'inherit' },
      grid: { vertLines: { color: '#232329' }, horzLines: { color: '#232329' } },
      rightPriceScale: { borderColor: '#2c2c34' },
      timeScale: { borderColor: '#2c2c34' },
      crosshair: { mode: 0 },
    })
    const price = chart.addSeries(LineSeries, { color: '#757a85', lineWidth: 1, lastValueVisible: false, priceLineVisible: false })
    const limit = chart.addSeries(LineSeries, { color: '#3182f6', lineWidth: 2, lastValueVisible: false, priceLineVisible: false })
    const daily = chart.addSeries(LineSeries, { color: '#f5a623', lineWidth: 2, lastValueVisible: false, priceLineVisible: false })

    const toLine = (key: 'price' | 'limitAvg' | 'dailyAvg'): LineData[] =>
      series
        .filter((s) => s[key] != null)
        .map((s) => ({ time: s.date as Time, value: s[key] as number }))
    price.setData(toLine('price'))
    limit.setData(toLine('limitAvg'))
    daily.setData(toLine('dailyAvg'))
    chart.timeScale().fitContent()
    chartRef.current = chart

    const ro = new ResizeObserver(() => ref.current && chart.applyOptions({ width: ref.current.clientWidth }))
    ro.observe(ref.current)
    return () => {
      ro.disconnect()
      chart.remove()
    }
  }, [series])

  return (
    <div>
      <div className="legend">
        <span><i style={{ background: '#757a85' }} />종가</span>
        <span><i style={{ background: '#3182f6' }} />지정가 적립 평단</span>
        <span><i style={{ background: '#f5a623' }} />단순 적립 평단</span>
      </div>
      <div ref={ref} style={{ width: '100%' }} />
    </div>
  )
}
