import { useEffect, useState, useMemo, useRef } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import ReactECharts from 'echarts-for-react'
import { ArrowLeft, TrendingUp, TrendingDown, Info, BarChart3, Activity } from 'lucide-react'
import Loading from '../components/Loading'
import StockTagNotePanel from '../components/StockTagNotePanel'
import { api } from '../lib/api'

interface StockInfo {
    id: number
    symbol: string
    name: string
    market: string
    industry: string | null
    market_cap: number | null
    pe_ratio: number | null
    pb_ratio: number | null
}

interface PricePoint {
    trade_date: string
    open: number
    high: number
    low: number
    close: number
    volume: number
    amount: number | null
}

export default function StockDetail() {
    const { symbol } = useParams<{ symbol: string }>()
    const navigate = useNavigate()
    const [searchParams] = useSearchParams()
    const noteId = searchParams.get('note')
    
    const [loading, setLoading] = useState(true)
    const [stock, setStock] = useState<StockInfo | null>(null)
    const [prices, setPrices] = useState<PricePoint[]>([])
    
    const notePanelRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        if (!symbol) return
        setLoading(true)
        Promise.all([
            api.get('/stocks', { params: { keyword: symbol, limit: 1 } }),
            api.post('/data/price_range', {
                symbol,
                start_date: '2024-01-01',
                end_date: new Date().toISOString().split('T')[0],
                frequency: 'D',
            }).catch(() => ({ data: [] })),
        ]).then(([stockRes, priceRes]) => {
            const stockItem = stockRes.data.items?.find((s: any) => s.symbol === symbol)
            setStock(stockItem || null)
            setPrices(priceRes.data || [])
        }).finally(() => setLoading(false))
    }, [symbol])

    useEffect(() => {
        if (noteId && notePanelRef.current) {
            setTimeout(() => {
                notePanelRef.current?.scrollIntoView({ behavior: 'smooth' })
            }, 500)
        }
    }, [noteId, loading])

    const latestPrice = useMemo(() => {
        if (prices.length === 0) return null
        return prices[prices.length - 1]
    }, [prices])

    const dailyChange = useMemo(() => {
        if (prices.length < 2) return null
        const today = prices[prices.length - 1]
        const yesterday = prices[prices.length - 2]
        return ((today.close - yesterday.close) / yesterday.close) * 100
    }, [prices])

    const klineOption = useMemo(() => {
        if (prices.length === 0) return {}

        const data = prices
        const categories = data.map(item => item.trade_date)
        const values = data.map(item => [item.open, item.close, item.low, item.high])
        const volumes = data.map((item, index) => [index, item.volume, item.close > item.open ? 1 : -1])

        const calculateMA = (dayCount: number) => {
            const result: (string | number)[] = []
            for (let i = 0; i < data.length; i++) {
                if (i < dayCount) {
                    result.push('-')
                    continue
                }
                let sum = 0
                for (let j = 0; j < dayCount; j++) {
                    sum += data[i - j].close
                }
                result.push((sum / dayCount).toFixed(2))
            }
            return result
        }

        return {
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'cross' },
                backgroundColor: 'rgba(255,255,255,0.95)',
                borderColor: '#e2e8f0',
                borderWidth: 1,
                textStyle: { color: '#1e293b', fontSize: 12 },
            },
            axisPointer: { link: { xAxisIndex: 'all' } },
            grid: [
                { left: '8%', right: '4%', height: '55%' },
                { left: '8%', right: '4%', top: '72%', height: '18%' }
            ],
            xAxis: [
                { type: 'category', data: categories, boundaryGap: false, axisLabel: { show: false }, axisLine: { lineStyle: { color: '#e2e8f0' } } },
                { type: 'category', gridIndex: 1, data: categories, boundaryGap: false, axisLabel: { fontSize: 10, color: '#94a3b8' }, axisLine: { lineStyle: { color: '#e2e8f0' } } }
            ],
            yAxis: [
                { scale: true, splitArea: { show: true, areaStyle: { color: ['rgba(248,250,252,0.5)', 'rgba(255,255,255,0.5)'] } }, axisLabel: { fontSize: 11, color: '#64748b' }, splitLine: { lineStyle: { color: '#f1f5f9' } } },
                { scale: true, gridIndex: 1, splitNumber: 2, axisLabel: { show: false }, axisLine: { show: false }, splitLine: { show: false } }
            ],
            dataZoom: [
                { type: 'inside', xAxisIndex: [0, 1], start: 50, end: 100 },
                { show: true, xAxisIndex: [0, 1], type: 'slider', top: '93%', height: 20, borderColor: '#e2e8f0', fillerColor: 'rgba(59,130,246,0.1)', handleStyle: { color: '#3b82f6' } }
            ],
            series: [
                {
                    name: 'K线',
                    type: 'candlestick',
                    data: values,
                    itemStyle: {
                        color: '#ef4444',
                        color0: '#10b981',
                        borderColor: '#ef4444',
                        borderColor0: '#10b981',
                    },
                },
                {
                    name: 'MA5',
                    type: 'line',
                    data: calculateMA(5),
                    smooth: true,
                    lineStyle: { width: 1.5, color: '#f59e0b' },
                    showSymbol: false,
                },
                {
                    name: 'MA10',
                    type: 'line',
                    data: calculateMA(10),
                    smooth: true,
                    lineStyle: { width: 1.5, color: '#8b5cf6' },
                    showSymbol: false,
                },
                {
                    name: 'MA20',
                    type: 'line',
                    data: calculateMA(20),
                    smooth: true,
                    lineStyle: { width: 1.5, color: '#06b6d4' },
                    showSymbol: false,
                },
                {
                    name: '成交量',
                    type: 'bar',
                    xAxisIndex: 1,
                    yAxisIndex: 1,
                    data: volumes,
                    itemStyle: {
                        color: (params: any) => {
                            return params.data[2] > 0 ? 'rgba(239,68,68,0.6)' : 'rgba(16,185,129,0.6)'
                        }
                    }
                },
            ],
            legend: {
                data: ['K线', 'MA5', 'MA10', 'MA20'],
                top: 10,
                right: 20,
                textStyle: { fontSize: 11, color: '#64748b' },
                itemWidth: 14,
                itemHeight: 10,
            },
        }
    }, [prices])

    const formatNumber = (num: number | null, decimals: number = 2) => {
        if (num === null || num === undefined) return '--'
        if (Math.abs(num) >= 1e8) return (num / 1e8).toFixed(2) + '亿'
        if (Math.abs(num) >= 1e4) return (num / 1e4).toFixed(2) + '万'
        return num.toFixed(decimals)
    }

    const formatChange = (val: number | null) => {
        if (val === null || val === undefined) return '--'
        const sign = val >= 0 ? '+' : ''
        return `${sign}${val.toFixed(2)}%`
    }

    const getChangeColor = (val: number | null) => {
        if (val === null || val === undefined) return 'text-slate-400'
        if (val > 0) return 'text-red-500'
        if (val < 0) return 'text-emerald-500'
        return 'text-slate-400'
    }

    if (loading) {
        return (
            <div className="h-full flex items-center justify-center">
                <Loading />
            </div>
        )
    }

    if (!stock) {
        return (
            <div className="h-full flex flex-col items-center justify-center gap-4">
                <div className="text-muted-foreground">股票不存在</div>
                <button
                    onClick={() => navigate(-1)}
                    className="text-primary hover:underline text-sm"
                >
                    返回上一页
                </button>
            </div>
        )
    }

    return (
        <div className="flex h-[calc(100vh-4rem)] -mx-8 -mt-8 -mb-8">
            <div className="flex-1 overflow-y-auto scrollbar-thin">
                <div className="p-8">
                    <button
                        onClick={() => navigate(-1)}
                        className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors mb-6"
                    >
                        <ArrowLeft size={16} />
                        返回
                    </button>

                    <div className="flex items-start justify-between mb-8">
                        <div>
                            <div className="flex items-center gap-3 mb-2">
                                <h1 className="text-2xl font-bold">{stock.name}</h1>
                                <span className={`px-2 py-0.5 rounded text-xs font-medium ${stock.market === 'SH' ? 'bg-red-50 text-red-600' : 'bg-blue-50 text-blue-600'}`}>
                                    {stock.market}
                                </span>
                                <span className="text-sm text-muted-foreground font-mono">{stock.symbol}</span>
                            </div>
                            {latestPrice && (
                                <div className="flex items-baseline gap-4">
                                    <span className={`text-3xl font-bold tabular-nums ${getChangeColor(dailyChange)}`}>
                                        {latestPrice.close.toFixed(2)}
                                    </span>
                                    <span className={`text-sm font-medium flex items-center gap-1 ${getChangeColor(dailyChange)}`}>
                                        {dailyChange && dailyChange >= 0 ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
                                        {formatChange(dailyChange)}
                                    </span>
                                </div>
                            )}
                        </div>
                    </div>

                    <div className="grid grid-cols-4 gap-4 mb-8">
                        <div className="bg-card rounded-xl border border-border p-4">
                            <div className="text-xs text-muted-foreground mb-1 flex items-center gap-1.5">
                                <BarChart3 size={12} />
                                总市值
                            </div>
                            <div className="text-lg font-semibold tabular-nums">
                                {formatNumber(stock.market_cap)}
                            </div>
                        </div>
                        <div className="bg-card rounded-xl border border-border p-4">
                            <div className="text-xs text-muted-foreground mb-1 flex items-center gap-1.5">
                                <Activity size={12} />
                                市盈率
                            </div>
                            <div className="text-lg font-semibold tabular-nums">
                                {stock.pe_ratio ? stock.pe_ratio.toFixed(2) : '--'}
                            </div>
                        </div>
                        <div className="bg-card rounded-xl border border-border p-4">
                            <div className="text-xs text-muted-foreground mb-1 flex items-center gap-1.5">
                                <Info size={12} />
                                市净率
                            </div>
                            <div className="text-lg font-semibold tabular-nums">
                                {stock.pb_ratio ? stock.pb_ratio.toFixed(2) : '--'}
                            </div>
                        </div>
                        <div className="bg-card rounded-xl border border-border p-4">
                            <div className="text-xs text-muted-foreground mb-1 flex items-center gap-1.5">
                                <TrendingUp size={12} />
                                所属行业
                            </div>
                            <div className="text-lg font-semibold truncate">
                                {stock.industry || '--'}
                            </div>
                        </div>
                    </div>

                    <div className="bg-card rounded-xl border border-border p-6">
                        <h3 className="text-base font-semibold mb-4 flex items-center gap-2">
                            <BarChart3 size={18} className="text-primary" />
                            K线走势
                        </h3>
                        {prices.length > 0 ? (
                            <ReactECharts
                                option={klineOption}
                                style={{ height: '400px' }}
                                notMerge={true}
                            />
                        ) : (
                            <div className="h-[400px] flex items-center justify-center text-muted-foreground text-sm">
                                暂无行情数据，请先同步日线数据
                            </div>
                        )}
                    </div>
                </div>
            </div>

            <div ref={notePanelRef}>
                <StockTagNotePanel symbol={symbol} stockName={stock.name} />
            </div>
        </div>
    )
}
