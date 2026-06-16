import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import ReactECharts from 'echarts-for-react'
import { TrendingUp, TrendingDown, Activity, BarChart2, DollarSign, Zap, PieChart } from 'lucide-react'
import Loading from '../components/Loading'
import { api } from '../lib/api'
import Select from '../components/Select'

interface SparklinePoint {
    date: string
    value: number
}

interface LeaderboardItem {
    symbol: string
    name: string
    market: string | null
    industry: string | null
    latest_price: number | null
    change_pct: number | null
    turnover_rate: number | null
    amplitude: number | null
    net_inflow: number | null
    strong_score: number | null
    rsi: number | null
    ma5: number | null
    ma10: number | null
    ma20: number | null
    sparkline: SparklinePoint[] | null
}

interface MarketDistribution {
    name: string
    value: number
}

interface LeaderboardData {
    items: LeaderboardItem[]
    market_distribution: MarketDistribution[]
    total: number
    latest_date: string | null
    dimension: string | null
    period: number | null
    market: string | null
}

interface DimensionInfo {
    key: string
    name: string
    description: string
    icon: any
}

const DIMENSIONS: DimensionInfo[] = [
    { key: 'gain', name: '涨幅榜', description: '涨幅最大的股票', icon: TrendingUp },
    { key: 'loss', name: '跌幅榜', description: '跌幅最大的股票', icon: TrendingDown },
    { key: 'turnover', name: '换手率榜', description: '交易最活跃的股票', icon: Activity },
    { key: 'amplitude', name: '振幅榜', description: '价格波动最大的股票', icon: BarChart2 },
    { key: 'inflow', name: '资金净流入榜', description: '资金流入最多的股票', icon: DollarSign },
    { key: 'strong', name: '强势股榜', description: '综合强势的股票', icon: Zap },
]

const PERIOD_OPTIONS = [
    { value: '1', label: '当日' },
    { value: '5', label: '5日累计' },
    { value: '20', label: '20日累计' },
]

const MARKET_OPTIONS = [
    { value: 'all', label: '全部市场' },
    { value: 'sh', label: '沪市' },
    { value: 'sz', label: '深市' },
    { value: 'cyb', label: '创业板' },
]

export default function Leaderboard() {
    const navigate = useNavigate()
    const [loading, setLoading] = useState(true)
    const [activeDimension, setActiveDimension] = useState('gain')
    const [period, setPeriod] = useState('1')
    const [market, setMarket] = useState('all')
    const [data, setData] = useState<LeaderboardData | null>(null)

    const fetchLeaderboard = () => {
        setLoading(true)
        api.get(`/leaderboard/${activeDimension}`, {
            params: {
                period: parseInt(period),
                market,
                limit: 50,
            }
        }).then(res => {
            setData(res.data)
        }).finally(() => setLoading(false))
    }

    useEffect(() => {
        fetchLeaderboard()
    }, [activeDimension, period, market])

    const formatChange = (val: number | null | undefined) => {
        if (val === null || val === undefined) return '--'
        const sign = val >= 0 ? '+' : ''
        return `${sign}${val.toFixed(2)}%`
    }

    const getChangeColor = (val: number | null | undefined) => {
        if (val === null || val === undefined) return 'text-slate-400'
        if (val > 0) return 'text-red-500'
        if (val < 0) return 'text-emerald-500'
        return 'text-slate-400'
    }

    const getChangeBgColor = (val: number | null | undefined) => {
        if (val === null || val === undefined) return 'bg-slate-50'
        if (val > 0) return 'bg-red-50'
        if (val < 0) return 'bg-emerald-50'
        return 'bg-slate-50'
    }

    const getMarketLabel = (market: string | null, symbol: string) => {
        if (symbol?.startsWith('300')) return '创业板'
        if (market === 'SH') return '沪市'
        if (market === 'SZ') return '深市'
        return '--'
    }

    const pieChartOption = useMemo(() => {
        if (!data?.market_distribution) return {}
        const colors = ['#3b82f6', '#10b981', '#f59e0b']
        return {
            tooltip: {
                trigger: 'item',
                formatter: '{b}: {c}只 ({d}%)'
            },
            legend: {
                orient: 'vertical',
                right: '5%',
                top: 'center',
                itemWidth: 12,
                itemHeight: 12,
                textStyle: { fontSize: 12, color: '#64748b' }
            },
            series: [
                {
                    type: 'pie',
                    radius: ['50%', '70%'],
                    center: ['35%', '50%'],
                    avoidLabelOverlap: false,
                    itemStyle: {
                        borderRadius: 4,
                        borderColor: '#fff',
                        borderWidth: 2
                    },
                    label: {
                        show: false,
                        position: 'center'
                    },
                    emphasis: {
                        label: {
                            show: true,
                            fontSize: 14,
                            fontWeight: 'bold'
                        }
                    },
                    labelLine: {
                        show: false
                    },
                    data: data.market_distribution.map((item, index) => ({
                        name: item.name,
                        value: item.value,
                        itemStyle: { color: colors[index % colors.length] }
                    }))
                }
            ]
        }
    }, [data])

    const getSparklineOption = (sparkline: SparklinePoint[] | null) => {
        if (!sparkline || sparkline.length < 2) return {}
        const values = sparkline.map(d => d.value)
        const isUp = values[values.length - 1] >= values[0]
        const color = isUp ? '#ef4444' : '#10b981'
        return {
            grid: { top: 5, right: 5, bottom: 5, left: 5 },
            xAxis: {
                type: 'category',
                show: false,
                data: sparkline.map(d => d.date)
            },
            yAxis: {
                type: 'value',
                show: false,
                scale: true
            },
            series: [
                {
                    type: 'line',
                    data: values,
                    smooth: true,
                    symbol: 'none',
                    lineStyle: { color, width: 1.5 },
                    areaStyle: {
                        color: {
                            type: 'linear',
                            x: 0, y: 0, x2: 0, y2: 1,
                            colorStops: [
                                { offset: 0, color: isUp ? 'rgba(239,68,68,0.2)' : 'rgba(16,185,129,0.2)' },
                                { offset: 1, color: isUp ? 'rgba(239,68,68,0)' : 'rgba(16,185,129,0)' }
                            ]
                        }
                    }
                }
            ]
        }
    }

    const getMetricValue = (item: LeaderboardItem) => {
        switch (activeDimension) {
            case 'gain':
            case 'loss':
                return formatChange(item.change_pct)
            case 'turnover':
                return item.turnover_rate !== null && item.turnover_rate !== undefined
                    ? `${item.turnover_rate.toFixed(2)}%`
                    : '--'
            case 'amplitude':
                return item.amplitude !== null && item.amplitude !== undefined
                    ? `${item.amplitude.toFixed(2)}%`
                    : '--'
            case 'inflow':
                return item.net_inflow !== null && item.net_inflow !== undefined
                    ? `${item.net_inflow.toFixed(2)}亿`
                    : '--'
            case 'strong':
                return item.strong_score !== null && item.strong_score !== undefined
                    ? item.strong_score.toFixed(1)
                    : '--'
            default:
                return '--'
        }
    }

    const getMetricLabel = () => {
        switch (activeDimension) {
            case 'gain':
            case 'loss':
                return '涨跌幅'
            case 'turnover':
                return '换手率'
            case 'amplitude':
                return '振幅'
            case 'inflow':
                return '净流入'
            case 'strong':
                return '强势分'
            default:
                return '指标'
        }
    }

    const handleRowClick = (symbol: string) => {
        navigate(`/stock/${symbol}`)
    }

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-2xl font-bold tracking-tight text-slate-900">多维排行榜</h2>
                <p className="text-sm text-slate-500 mt-1">
                    跨多个市场维度查看股票表现，发现市场机会
                    {data?.latest_date && <span className="ml-2">（数据日期：{data.latest_date}）</span>}
                </p>
            </div>

            <div className="flex flex-wrap items-center gap-4">
                <div className="flex bg-white rounded-xl p-1 shadow-sm border border-slate-100">
                    {DIMENSIONS.map(dim => {
                        const Icon = dim.icon
                        const isActive = activeDimension === dim.key
                        return (
                            <button
                                key={dim.key}
                                onClick={() => setActiveDimension(dim.key)}
                                className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-lg transition-all duration-200 ${
                                    isActive
                                        ? 'bg-primary text-white shadow-md shadow-blue-500/20'
                                        : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'
                                }`}
                            >
                                <Icon size={16} />
                                <span>{dim.name}</span>
                            </button>
                        )
                    })}
                </div>

                <div className="flex items-center gap-3 ml-auto">
                    <div className="w-32">
                        <Select
                            value={period}
                            onChange={setPeriod}
                            options={PERIOD_OPTIONS}
                            placeholder="时间窗口"
                        />
                    </div>
                    <div className="w-36">
                        <Select
                            value={market}
                            onChange={setMarket}
                            options={MARKET_OPTIONS}
                            placeholder="市场筛选"
                        />
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                <div className="lg:col-span-1">
                    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
                        <div className="flex items-center gap-2 mb-4">
                            <PieChart size={18} className="text-slate-400" />
                            <h3 className="text-sm font-semibold text-slate-700">市场分布</h3>
                        </div>
                        <ReactECharts
                            option={pieChartOption}
                            style={{ height: 200 }}
                            opts={{ renderer: 'svg' }}
                        />
                        <div className="mt-2 text-center">
                            <span className="text-2xl font-bold text-slate-900">{data?.total || 0}</span>
                            <span className="text-sm text-slate-500 ml-1">只股票</span>
                        </div>
                    </div>
                </div>

                <div className="lg:col-span-3">
                    <div className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden">
                        {loading ? (
                            <div className="h-[600px] flex items-center justify-center">
                                <Loading />
                            </div>
                        ) : (
                            <div className="overflow-x-auto">
                                <table className="w-full">
                                    <thead className="bg-slate-50/80 border-b border-slate-100">
                                        <tr>
                                            <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider w-16">
                                                排名
                                            </th>
                                            <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                                                股票
                                            </th>
                                            <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider w-24">
                                                市场
                                            </th>
                                            <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wider w-28">
                                                最新价
                                            </th>
                                            <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wider w-28">
                                                {getMetricLabel()}
                                            </th>
                                            <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wider w-28">
                                                涨跌幅
                                            </th>
                                            <th className="px-4 py-3 text-center text-xs font-semibold text-slate-500 uppercase tracking-wider w-40">
                                                走势
                                            </th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-50">
                                        {data?.items.map((item, index) => (
                                            <tr
                                                key={item.symbol}
                                                className={`cursor-pointer transition-colors hover:bg-slate-50/50 ${getChangeBgColor(item.change_pct)}`}
                                                onClick={() => handleRowClick(item.symbol)}
                                            >
                                                <td className="px-4 py-3">
                                                    <span className={`inline-flex items-center justify-center w-6 h-6 rounded-md text-xs font-bold ${
                                                        index < 3
                                                            ? 'bg-gradient-to-br from-amber-400 to-orange-500 text-white'
                                                            : 'bg-slate-100 text-slate-500'
                                                    }`}>
                                                        {index + 1}
                                                    </span>
                                                </td>
                                                <td className="px-4 py-3">
                                                    <div className="font-medium text-slate-900">{item.name}</div>
                                                    <div className="text-xs text-slate-400 mt-0.5">{item.symbol}</div>
                                                    {item.industry && (
                                                        <div className="text-xs text-slate-400 mt-0.5">{item.industry}</div>
                                                    )}
                                                </td>
                                                <td className="px-4 py-3">
                                                    <span className={`inline-block px-2 py-0.5 text-xs rounded-full ${
                                                        item.symbol?.startsWith('300')
                                                            ? 'bg-amber-50 text-amber-600'
                                                            : item.market === 'SH'
                                                            ? 'bg-blue-50 text-blue-600'
                                                            : 'bg-emerald-50 text-emerald-600'
                                                    }`}>
                                                        {getMarketLabel(item.market, item.symbol || '')}
                                                    </span>
                                                </td>
                                                <td className="px-4 py-3 text-right font-medium text-slate-700">
                                                    {item.latest_price ? item.latest_price.toFixed(2) : '--'}
                                                </td>
                                                <td className={`px-4 py-3 text-right font-bold ${
                                                    activeDimension === 'loss'
                                                        ? 'text-emerald-500'
                                                        : activeDimension === 'gain'
                                                        ? 'text-red-500'
                                                        : 'text-slate-700'
                                                }`}>
                                                    {getMetricValue(item)}
                                                </td>
                                                <td className={`px-4 py-3 text-right font-medium ${getChangeColor(item.change_pct)}`}>
                                                    {formatChange(item.change_pct)}
                                                </td>
                                                <td className="px-4 py-3">
                                                    <div className="h-12">
                                                        <ReactECharts
                                                            option={getSparklineOption(item.sparkline)}
                                                            style={{ height: '100%', width: '100%' }}
                                                            opts={{ renderer: 'svg' }}
                                                        />
                                                    </div>
                                                </td>
                                            </tr>
                                        ))}
                                        {(!data?.items || data.items.length === 0) && (
                                            <tr>
                                                <td colSpan={7} className="px-4 py-12 text-center text-slate-400">
                                                    暂无数据
                                                </td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}
