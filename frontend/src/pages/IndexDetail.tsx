import { useEffect, useState, useMemo } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import ReactECharts from 'echarts-for-react'
import { ArrowLeft, CandlestickChart, TrendingUp, TrendingDown, BarChart2, Activity, Target, GitCompare, Timer, Layers } from 'lucide-react'
import Loading from '../components/Loading'
import { api } from '../lib/api'

interface HistoryItem {
    trade_date: string
    open: number
    high: number
    low: number
    close: number
    volume: number
    amount: number | null
    ma5: number | null
    ma10: number | null
    ma20: number | null
    ma60: number | null
}

interface IndexDetailData {
    id: number
    code: string
    name: string
    index_type: 'index' | 'etf'
    tracking_target: string | null
    list_date: string | null
    daily_change: number | null
    five_day_change: number | null
    latest_close: number | null
    latest_high: number | null
    latest_low: number | null
    latest_open: number | null
    latest_volume: number | null
    latest_amount: number | null
    metrics: {
        ytd_return: number | null
        year_return: number | null
        month_return: number | null
        week_return: number | null
        volatility_20d: number | null
        volatility_60d: number | null
        high_52w: number | null
        low_52w: number | null
        avg_volume_20d: number | null
    }
}

interface ConstituentItem {
    symbol: string
    name: string
    weight: number | null
    market: string | null
    industry: string | null
    latest_price: number | null
    daily_change: number | null
}

export default function IndexDetail() {
    const { code } = useParams<{ code: string }>()
    const navigate = useNavigate()
    const [searchParams] = useSearchParams()
    const [loading, setLoading] = useState(true)
    const [detail, setDetail] = useState<IndexDetailData | null>(null)
    const [history, setHistory] = useState<HistoryItem[]>([])
    const [constituents, setConstituents] = useState<ConstituentItem[]>([])
    const [activeTab, setActiveTab] = useState<'kline' | 'constituents'>('kline')
    const [maOptions, setMaOptions] = useState({ ma5: true, ma10: true, ma20: true, ma60: false })

    useEffect(() => {
        if (!code) return
        setLoading(true)
        Promise.all([
            api.get(`/index/${code}/detail`),
            api.get(`/index/${code}/history`, { params: { limit: 500 } }),
            api.get(`/index/constituents/${code}`).catch(() => ({ data: { items: [] } })),
        ]).then(([detailRes, historyRes, consRes]) => {
            setDetail(detailRes.data)
            setHistory(historyRes.data.items || [])
            setConstituents(consRes.data?.items || [])
        }).finally(() => setLoading(false))
    }, [code])

    const formatChange = (val: number | null) => {
        if (val === null || val === undefined || isNaN(val as number)) return '--'
        const sign = val >= 0 ? '+' : ''
        return `${sign}${val.toFixed(2)}%`
    }

    const getChangeColor = (val: number | null) => {
        if (val === null || val === undefined || isNaN(val as number)) return 'text-slate-400'
        if (val > 0) return 'text-red-500'
        if (val < 0) return 'text-emerald-500'
        return 'text-slate-400'
    }

    const formatNumber = (val: number | null, digits = 2) => {
        if (val === null || val === undefined) return '--'
        return val.toFixed(digits)
    }

    const formatVolume = (val: number | null) => {
        if (val === null || val === undefined) return '--'
        if (val >= 1e8) return `${(val / 1e8).toFixed(2)}亿`
        if (val >= 1e4) return `${(val / 1e4).toFixed(2)}万`
        return val.toFixed(0)
    }

    const handleBacktestAsBenchmark = () => {
        if (!detail) return
        const today = new Date()
        const oneYearAgo = new Date()
        oneYearAgo.setFullYear(today.getFullYear() - 1)
        const params = new URLSearchParams({
            strategy: searchParams.get('strategy') || 'dual_ma',
            symbols: detail.tracking_target || detail.code,
            start: searchParams.get('start') || oneYearAgo.toISOString().split('T')[0],
            end: searchParams.get('end') || today.toISOString().split('T')[0],
            benchmark: detail.code,
        })
        navigate(`/backtest?${params.toString()}`)
    }

    const handleCompareWithOther = () => {
        navigate('/index-compare')
    }

    const klineOption = useMemo(() => {
        if (!history || history.length === 0) return {}

        const categories = history.map(item => item.trade_date)
        const values = history.map(item => [item.open, item.close, item.low, item.high])
        const volumes = history.map((item, index) => [
            index, item.volume, item.close >= item.open ? 1 : -1
        ])

        const getMAData = (key: keyof typeof maOptions, maKey: 'ma5' | 'ma10' | 'ma20' | 'ma60') => {
            if (!maOptions[key]) return null
            const data = history.map(item => {
                const v = item[maKey]
                return v !== null && v !== undefined ? v.toFixed(2) : '-'
            })
            return data
        }

        const ma5Data = getMAData('ma5', 'ma5')
        const ma10Data = getMAData('ma10', 'ma10')
        const ma20Data = getMAData('ma20', 'ma20')
        const ma60Data = getMAData('ma60', 'ma60')

        const series: any[] = [
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
        ]

        if (ma5Data) {
            series.push({
                name: 'MA5',
                type: 'line',
                data: ma5Data,
                smooth: true,
                showSymbol: false,
                lineStyle: { opacity: 0.8, width: 1.5 },
                itemStyle: { color: '#f59e0b' },
            })
        }
        if (ma10Data) {
            series.push({
                name: 'MA10',
                type: 'line',
                data: ma10Data,
                smooth: true,
                showSymbol: false,
                lineStyle: { opacity: 0.8, width: 1.5 },
                itemStyle: { color: '#3b82f6' },
            })
        }
        if (ma20Data) {
            series.push({
                name: 'MA20',
                type: 'line',
                data: ma20Data,
                smooth: true,
                showSymbol: false,
                lineStyle: { opacity: 0.8, width: 1.5 },
                itemStyle: { color: '#8b5cf6' },
            })
        }
        if (ma60Data) {
            series.push({
                name: 'MA60',
                type: 'line',
                data: ma60Data,
                smooth: true,
                showSymbol: false,
                lineStyle: { opacity: 0.8, width: 1.5 },
                itemStyle: { color: '#ec4899' },
            })
        }

        series.push({
            name: '成交量',
            type: 'bar',
            xAxisIndex: 1,
            yAxisIndex: 1,
            data: volumes,
            itemStyle: {
                color: (params: any) => params.data[2] > 0 ? '#ef4444' : '#10b981',
                opacity: 0.6,
            }
        })

        return {
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'cross' },
                formatter: (params: any) => {
                    const kline = params.find((p: any) => p.seriesName === 'K线')
                    if (!kline) return ''
                    const d = kline.data
                    const dateStr = kline.axisValueLabel
                    let html = `<div class="font-medium">${dateStr}</div>`
                    html += `<div class="text-xs mt-1 space-y-0.5">`
                    html += `开盘: ${d[1]}<br/>`
                    html += `收盘: ${d[2]}<br/>`
                    html += `最高: ${d[4]}<br/>`
                    html += `最低: ${d[3]}<br/>`
                    for (const p of params) {
                        if (p.seriesType === 'line' && p.data !== '-') {
                            html += `${p.seriesName}: ${p.data}<br/>`
                        }
                    }
                    html += `</div>`
                    return html
                }
            },
            axisPointer: { link: { xAxisIndex: 'all' } },
            legend: {
                data: ['K线', maOptions.ma5 ? 'MA5' : null, maOptions.ma10 ? 'MA10' : null, maOptions.ma20 ? 'MA20' : null, maOptions.ma60 ? 'MA60' : null].filter(Boolean),
                top: 5,
            },
            grid: [
                { left: '8%', right: '4%', height: '55%' },
                { left: '8%', right: '4%', top: '72%', height: '18%' }
            ],
            xAxis: [
                { type: 'category', data: categories, boundaryGap: false, axisLabel: { show: false } },
                { type: 'category', gridIndex: 1, data: categories, boundaryGap: false, axisLabel: { fontSize: 10, rotate: 30 } }
            ],
            yAxis: [
                { scale: true, splitArea: { show: true }, axisLabel: { fontSize: 11 } },
                { scale: true, gridIndex: 1, splitNumber: 2, axisLabel: { show: false }, axisLine: { show: false }, splitLine: { show: false } }
            ],
            dataZoom: [
                { type: 'inside', xAxisIndex: [0, 1], start: 30, end: 100 },
                { show: true, xAxisIndex: [0, 1], type: 'slider', top: '93%', height: 20 }
            ],
            series,
        }
    }, [history, maOptions])

    if (loading) {
        return <div className="space-y-6"><div className="p-12"><Loading /></div></div>
    }

    if (!detail) {
        return <div className="space-y-6"><div className="p-12 text-center text-slate-400">指数/ETF不存在</div></div>
    }

    const metricCards = [
        { label: '最新价', value: detail.latest_close, format: (v: any) => formatNumber(v), color: 'text-slate-900', icon: BarChart2, bg: 'bg-slate-50' },
        { label: '当日涨跌', value: detail.daily_change, format: formatChange, color: getChangeColor(detail.daily_change), icon: detail.daily_change && detail.daily_change >= 0 ? TrendingUp : TrendingDown, bg: detail.daily_change && detail.daily_change >= 0 ? 'bg-red-50' : 'bg-emerald-50' },
        { label: '5日涨跌', value: detail.five_day_change, format: formatChange, color: getChangeColor(detail.five_day_change), icon: Activity, bg: 'bg-blue-50' },
        { label: '月涨跌', value: detail.metrics?.month_return, format: formatChange, color: getChangeColor(detail.metrics?.month_return), icon: BarChart2, bg: 'bg-purple-50' },
        { label: '年涨跌', value: detail.metrics?.year_return, format: formatChange, color: getChangeColor(detail.metrics?.year_return), icon: TrendingUp, bg: 'bg-amber-50' },
        { label: '波动率20D', value: detail.metrics?.volatility_20d, format: (v: any) => formatNumber(v) + '%', color: 'text-slate-700', icon: Activity, bg: 'bg-cyan-50' },
        { label: '52周最高', value: detail.metrics?.high_52w, format: (v: any) => formatNumber(v), color: 'text-red-600', icon: Target, bg: 'bg-red-50' },
        { label: '52周最低', value: detail.metrics?.low_52w, format: (v: any) => formatNumber(v), color: 'text-emerald-600', icon: Target, bg: 'bg-emerald-50' },
    ]

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <button
                        onClick={() => navigate('/index')}
                        className="h-10 w-10 rounded-xl border-2 border-slate-200 flex items-center justify-center hover:border-primary/50 hover:text-primary transition-colors"
                    >
                        <ArrowLeft size={18} />
                    </button>
                    <div>
                        <div className="flex items-center gap-3">
                            <h2 className="text-2xl font-bold tracking-tight text-slate-900">{detail.name}</h2>
                            <span className={`inline-flex items-center px-2 py-0.5 rounded-lg text-xs font-medium ${
                                detail.index_type === 'index'
                                    ? 'bg-blue-50 text-blue-600'
                                    : 'bg-purple-50 text-purple-600'
                            }`}>
                                {detail.index_type === 'index' ? '指数' : 'ETF'}
                            </span>
                        </div>
                        <p className="text-sm text-slate-500 mt-0.5">
                            {detail.code}
                            {detail.tracking_target && ` · 跟踪标的: ${detail.tracking_target}`}
                            {detail.list_date && ` · 上市日期: ${detail.list_date}`}
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={handleCompareWithOther}
                        className="flex items-center gap-2 h-10 px-4 rounded-xl border-2 border-slate-200 text-sm font-medium text-slate-600 hover:border-primary hover:text-primary transition-colors"
                    >
                        <GitCompare size={16} />
                        加入对比
                    </button>
                    <button
                        onClick={handleBacktestAsBenchmark}
                        className="flex items-center gap-2 h-10 px-4 rounded-xl bg-primary text-white text-sm font-medium shadow-sm hover:bg-primary/90 transition-colors"
                    >
                        <Timer size={16} />
                        作为回测基准
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-4 gap-4">
                {metricCards.slice(0, 4).map((card, idx) => {
                    const Icon = card.icon
                    return (
                        <div key={idx} className="group relative overflow-hidden rounded-2xl bg-white border border-slate-200/60 p-4 shadow-sm">
                            <div className="flex items-center justify-between">
                                <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">{card.label}</p>
                                <div className={`h-8 w-8 rounded-lg ${card.bg} flex items-center justify-center`}>
                                    <Icon size={14} className={card.color} />
                                </div>
                            </div>
                            <p className={`text-2xl font-bold mt-2 ${card.color}`}>
                                {card.format(card.value)}
                            </p>
                        </div>
                    )
                })}
            </div>

            <div className="grid grid-cols-4 gap-4">
                {metricCards.slice(4).map((card, idx) => {
                    const Icon = card.icon
                    return (
                        <div key={idx} className="group relative overflow-hidden rounded-2xl bg-white border border-slate-200/60 p-4 shadow-sm">
                            <div className="flex items-center justify-between">
                                <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">{card.label}</p>
                                <div className={`h-8 w-8 rounded-lg ${card.bg} flex items-center justify-center`}>
                                    <Icon size={14} className={card.color} />
                                </div>
                            </div>
                            <p className={`text-2xl font-bold mt-2 ${card.color}`}>
                                {card.format(card.value)}
                            </p>
                        </div>
                    )
                })}
                <div className="group relative overflow-hidden rounded-2xl bg-white border border-slate-200/60 p-4 shadow-sm">
                    <div className="flex items-center justify-between">
                        <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">成交量</p>
                        <div className="h-8 w-8 rounded-lg bg-slate-50 flex items-center justify-center">
                            <BarChart2 size={14} className="text-slate-600" />
                        </div>
                    </div>
                    <p className="text-2xl font-bold mt-2 text-slate-900">
                        {formatVolume(detail.latest_volume)}
                    </p>
                </div>
                <div className="group relative overflow-hidden rounded-2xl bg-white border border-slate-200/60 p-4 shadow-sm">
                    <div className="flex items-center justify-between">
                        <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">成交额</p>
                        <div className="h-8 w-8 rounded-lg bg-indigo-50 flex items-center justify-center">
                            <Activity size={14} className="text-indigo-600" />
                        </div>
                    </div>
                    <p className="text-2xl font-bold mt-2 text-slate-900">
                        {formatVolume(detail.latest_amount)}
                    </p>
                </div>
                <div className="group relative overflow-hidden rounded-2xl bg-white border border-slate-200/60 p-4 shadow-sm">
                    <div className="flex items-center justify-between">
                        <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">年内涨跌</p>
                        <div className="h-8 w-8 rounded-lg bg-rose-50 flex items-center justify-center">
                            <TrendingUp size={14} className="text-rose-600" />
                        </div>
                    </div>
                    <p className={`text-2xl font-bold mt-2 ${getChangeColor(detail.metrics?.ytd_return)}`}>
                        {formatChange(detail.metrics?.ytd_return)}
                    </p>
                </div>
                <div className="group relative overflow-hidden rounded-2xl bg-white border border-slate-200/60 p-4 shadow-sm">
                    <div className="flex items-center justify-between">
                        <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">波动率60D</p>
                        <div className="h-8 w-8 rounded-lg bg-teal-50 flex items-center justify-center">
                            <Activity size={14} className="text-teal-600" />
                        </div>
                    </div>
                    <p className="text-2xl font-bold mt-2 text-slate-900">
                        {formatNumber(detail.metrics?.volatility_60d)}%
                    </p>
                </div>
            </div>

            <div className="flex gap-2 border-b border-slate-200">
                <button
                    onClick={() => setActiveTab('kline')}
                    className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                        activeTab === 'kline'
                            ? 'border-primary text-primary'
                            : 'border-transparent text-slate-500 hover:text-slate-700'
                    }`}
                >
                    <div className="flex items-center gap-2">
                        <CandlestickChart size={16} />
                        K线走势
                    </div>
                </button>
                <button
                    onClick={() => setActiveTab('constituents')}
                    className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                        activeTab === 'constituents'
                            ? 'border-primary text-primary'
                            : 'border-transparent text-slate-500 hover:text-slate-700'
                    }`}
                >
                    <div className="flex items-center gap-2">
                        <Layers size={16} />
                        成分股{constituents.length > 0 && ` (${constituents.length})`}
                    </div>
                </button>
            </div>

            {activeTab === 'kline' && (
                <div className="rounded-2xl border border-slate-200/60 bg-white p-5 shadow-sm">
                    <div className="flex items-center justify-between mb-4">
                        <div>
                            <h3 className="text-lg font-bold text-slate-900">{detail.name} 走势</h3>
                            <p className="text-xs text-slate-400 mt-1">共 {history.length} 个交易日</p>
                        </div>
                        <div className="flex items-center gap-3">
                            <span className="text-xs font-medium text-slate-500">均线:</span>
                            {[
                                { key: 'ma5', label: 'MA5', color: 'bg-amber-500' },
                                { key: 'ma10', label: 'MA10', color: 'bg-blue-500' },
                                { key: 'ma20', label: 'MA20', color: 'bg-purple-500' },
                                { key: 'ma60', label: 'MA60', color: 'bg-pink-500' },
                            ].map(item => (
                                <button
                                    key={item.key}
                                    onClick={() => setMaOptions({
                                        ...maOptions,
                                        [item.key]: !maOptions[item.key as keyof typeof maOptions],
                                    })}
                                    className={`flex items-center gap-1.5 h-7 px-2.5 rounded-lg text-xs font-medium transition-colors ${
                                        maOptions[item.key as keyof typeof maOptions]
                                            ? 'bg-slate-100 text-slate-700'
                                            : 'bg-slate-50 text-slate-400'
                                    }`}
                                >
                                    <span className={`h-2 w-2 rounded-full ${item.color}`} />
                                    {item.label}
                                </button>
                            ))}
                        </div>
                    </div>
                    {history.length > 0 ? (
                        <ReactECharts option={klineOption} style={{ height: 560 }} notMerge={true} />
                    ) : (
                        <div className="h-[560px] flex items-center justify-center text-slate-400">
                            暂无K线数据
                        </div>
                    )}
                </div>
            )}

            {activeTab === 'constituents' && (
                <div className="rounded-2xl border border-slate-200/60 bg-white shadow-sm overflow-hidden">
                    <div className="p-4 border-b border-slate-100">
                        <h3 className="text-lg font-bold text-slate-900">成分股列表</h3>
                        <p className="text-xs text-slate-400 mt-1">按权重排序（如有）</p>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead className="bg-slate-50/80">
                                <tr>
                                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">股票</th>
                                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">行业</th>
                                    <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wider">权重</th>
                                    <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wider">最新价</th>
                                    <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wider">涨跌幅</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                                {constituents.map((item) => (
                                    <tr key={item.symbol} className="hover:bg-slate-50/50 transition-colors">
                                        <td className="px-4 py-3.5">
                                            <div>
                                                <p className="text-sm font-semibold text-slate-900">{item.name}</p>
                                                <p className="text-xs text-slate-400">{item.symbol}</p>
                                            </div>
                                        </td>
                                        <td className="px-4 py-3.5">
                                            <span className="text-sm text-slate-600">{item.industry || '--'}</span>
                                        </td>
                                        <td className="px-4 py-3.5 text-right">
                                            <span className="text-sm font-medium text-slate-700">
                                                {item.weight !== null ? item.weight.toFixed(2) + '%' : '--'}
                                            </span>
                                        </td>
                                        <td className="px-4 py-3.5 text-right">
                                            <span className="text-sm font-medium text-slate-900">
                                                {item.latest_price !== null ? item.latest_price.toFixed(2) : '--'}
                                            </span>
                                        </td>
                                        <td className="px-4 py-3.5 text-right">
                                            <span className={`text-sm font-semibold ${getChangeColor(item.daily_change)}`}>
                                                {formatChange(item.daily_change)}
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                                {constituents.length === 0 && (
                                    <tr>
                                        <td colSpan={5} className="px-4 py-12 text-center text-slate-400">
                                            暂无成分股数据（可能为ETF产品或该指数暂不支持成分股查询）
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
        </div>
    )
}
