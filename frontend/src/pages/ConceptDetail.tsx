import { useEffect, useState, useMemo } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import ReactECharts from 'echarts-for-react'
import { ArrowLeft, Layers, TrendingUp, Users, BarChart2, Network } from 'lucide-react'
import Loading from '../components/Loading'
import { api } from '../lib/api'

interface IndexPoint {
    trade_date: string
    open: number
    high: number
    low: number
    close: number
    volume: number
}

interface ConstituentItem {
    symbol: string
    name: string
    market: string
    industry: string | null
    weight: number | null
    latest_price: number | null
    daily_change: number | null
}

interface RelatedConcept {
    code: string
    name: string
    category: string | null
    overlap_count: number
    daily_change: number | null
    constituent_count: number
}

interface ConceptDetail {
    id: number
    code: string
    name: string
    description: string | null
    category: string | null
    constituent_count: number
    daily_change: number | null
    five_day_change: number | null
    index_series: IndexPoint[]
    constituents: ConstituentItem[]
}

export default function ConceptDetail() {
    const { code } = useParams<{ code: string }>()
    const navigate = useNavigate()
    const [loading, setLoading] = useState(true)
    const [detail, setDetail] = useState<ConceptDetail | null>(null)
    const [relatedConcepts, setRelatedConcepts] = useState<RelatedConcept[]>([])
    const [activeTab, setActiveTab] = useState<'kline' | 'constituents' | 'related'>('kline')

    useEffect(() => {
        if (!code) return
        setLoading(true)
        Promise.all([
            api.get(`/concept/${code}/detail`),
            api.get(`/concept/${code}/related`, { params: { limit: 10 } }),
        ]).then(([detailRes, relatedRes]) => {
            setDetail(detailRes.data)
            setRelatedConcepts(relatedRes.data.items)
        }).finally(() => setLoading(false))
    }, [code])

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

    const klineOption = useMemo(() => {
        if (!detail?.index_series || detail.index_series.length === 0) return {}

        const data = detail.index_series
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
                formatter: (params: any) => {
                    const item = params.find((p: any) => p.seriesName === 'K线')
                    if (!item) return ''
                    const d = item.data
                    return `
                        <div class="font-medium">${item.name}</div>
                        <div class="text-xs mt-1">
                            开盘: ${d[1]}<br/>
                            收盘: ${d[2]}<br/>
                            最低: ${d[3]}<br/>
                            最高: ${d[4]}
                        </div>
                    `
                }
            },
            axisPointer: { link: { xAxisIndex: 'all' } },
            grid: [
                { left: '8%', right: '4%', height: '55%' },
                { left: '8%', right: '4%', top: '72%', height: '18%' }
            ],
            xAxis: [
                { type: 'category', data: categories, boundaryGap: false, axisLabel: { show: false } },
                { type: 'category', gridIndex: 1, data: categories, boundaryGap: false, axisLabel: { fontSize: 10 } }
            ],
            yAxis: [
                { scale: true, splitArea: { show: true }, axisLabel: { fontSize: 11 } },
                { scale: true, gridIndex: 1, splitNumber: 2, axisLabel: { show: false }, axisLine: { show: false }, splitLine: { show: false } }
            ],
            dataZoom: [
                { type: 'inside', xAxisIndex: [0, 1], start: 30, end: 100 },
                { show: true, xAxisIndex: [0, 1], type: 'slider', top: '93%', height: 20 }
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
                    lineStyle: { opacity: 0.6, width: 1.5 },
                    itemStyle: { color: '#f59e0b' },
                },
                {
                    name: 'MA20',
                    type: 'line',
                    data: calculateMA(20),
                    smooth: true,
                    lineStyle: { opacity: 0.6, width: 1.5 },
                    itemStyle: { color: '#8b5cf6' },
                },
                {
                    name: '成交量',
                    type: 'bar',
                    xAxisIndex: 1,
                    yAxisIndex: 1,
                    data: volumes,
                    itemStyle: {
                        color: (params: any) => {
                            return params.data[2] > 0 ? '#ef4444' : '#10b981'
                        }
                    }
                }
            ],
        }
    }, [detail?.index_series])

    const relatedGraphOption = useMemo(() => {
        if (relatedConcepts.length === 0 || !detail) return {}

        const nodes = [
            {
                name: detail.name,
                symbolSize: 60,
                category: 0,
                itemStyle: { color: '#3b82f6' },
                label: { show: true, fontSize: 14, fontWeight: 'bold' }
            },
            ...relatedConcepts.map((c) => ({
                name: c.name,
                symbolSize: 30 + (c.overlap_count / detail.constituent_count) * 40,
                category: 1,
                value: c.overlap_count,
                itemStyle: {
                    color: c.daily_change && c.daily_change >= 0 ? '#ef4444' : '#10b981'
                }
            }))
        ]

        const links = relatedConcepts.map(c => ({
            source: detail.name,
            target: c.name,
            value: c.overlap_count,
            lineStyle: {
                width: Math.max(1, (c.overlap_count / detail.constituent_count) * 8),
                opacity: 0.4,
            }
        }))

        return {
            tooltip: {
                formatter: (params: any) => {
                    if (params.dataType === 'node') {
                        const data = params.data
                        if (data.category === 0) {
                            return `<b>${data.name}</b><br/>当前板块`
                        }
                        const concept = relatedConcepts.find(c => c.name === data.name)
                        if (concept) {
                            return `<b>${concept.name}</b><br/>重叠成分股: ${concept.overlap_count}只<br/>当日涨跌: ${formatChange(concept.daily_change)}`
                        }
                    }
                    return ''
                }
            },
            legend: [{
                data: ['当前板块', '关联概念'],
                bottom: 0,
            }],
            series: [
                {
                    type: 'graph',
                    layout: 'force',
                    roam: true,
                    label: {
                        show: true,
                        position: 'right',
                        fontSize: 12,
                        formatter: '{b}'
                    },
                    draggable: true,
                    data: nodes,
                    links: links,
                    lineStyle: {
                        color: '#cbd5e1',
                        curveness: 0.1,
                    },
                    emphasis: {
                        focus: 'adjacency',
                        lineStyle: {
                            width: 3,
                        }
                    },
                    force: {
                        repulsion: 300,
                        edgeLength: [80, 200],
                        gravity: 0.1,
                    },
                    categories: [
                        { name: '当前板块' },
                        { name: '关联概念' },
                    ],
                }
            ]
        }
    }, [relatedConcepts, detail])

    if (loading) {
        return (
            <div className="space-y-6">
                <div className="p-12"><Loading /></div>
            </div>
        )
    }

    if (!detail) {
        return (
            <div className="space-y-6">
                <div className="p-12 text-center text-slate-400">
                    概念板块不存在
                </div>
            </div>
        )
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center gap-4">
                <button
                    onClick={() => navigate('/concept')}
                    className="h-10 w-10 rounded-xl border-2 border-slate-200 flex items-center justify-center hover:border-primary/50 hover:text-primary transition-colors"
                >
                    <ArrowLeft size={18} />
                </button>
                <div>
                    <h2 className="text-2xl font-bold tracking-tight text-slate-900">{detail.name}</h2>
                    <p className="text-sm text-slate-500 mt-0.5">{detail.code} · {detail.category || '未分类'}</p>
                </div>
            </div>

            <div className="grid grid-cols-4 gap-5">
                <div className="group relative overflow-hidden rounded-2xl bg-white border border-slate-200/60 p-5 shadow-sm">
                    <div className="relative z-10">
                        <div className="flex items-center justify-between">
                            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">当日涨跌幅</p>
                            <div className="bg-red-50 rounded-xl p-2">
                                <TrendingUp size={18} className="text-red-500" />
                            </div>
                        </div>
                        <div className="mt-4">
                            <span className={`text-3xl font-bold ${getChangeColor(detail.daily_change)}`}>
                                {formatChange(detail.daily_change)}
                            </span>
                        </div>
                    </div>
                </div>

                <div className="group relative overflow-hidden rounded-2xl bg-white border border-slate-200/60 p-5 shadow-sm">
                    <div className="relative z-10">
                        <div className="flex items-center justify-between">
                            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">5日涨跌幅</p>
                            <div className="bg-purple-50 rounded-xl p-2">
                                <BarChart2 size={18} className="text-purple-500" />
                            </div>
                        </div>
                        <div className="mt-4">
                            <span className={`text-3xl font-bold ${getChangeColor(detail.five_day_change)}`}>
                                {formatChange(detail.five_day_change)}
                            </span>
                        </div>
                    </div>
                </div>

                <div className="group relative overflow-hidden rounded-2xl bg-white border border-slate-200/60 p-5 shadow-sm">
                    <div className="relative z-10">
                        <div className="flex items-center justify-between">
                            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">成分股数量</p>
                            <div className="bg-blue-50 rounded-xl p-2">
                                <Users size={18} className="text-blue-500" />
                            </div>
                        </div>
                        <div className="mt-4">
                            <span className="text-3xl font-bold text-slate-900">
                                {detail.constituent_count}
                                <span className="text-sm font-normal text-slate-400 ml-1">只</span>
                            </span>
                        </div>
                    </div>
                </div>

                <div className="group relative overflow-hidden rounded-2xl bg-white border border-slate-200/60 p-5 shadow-sm">
                    <div className="relative z-10">
                        <div className="flex items-center justify-between">
                            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">关联概念</p>
                            <div className="bg-emerald-50 rounded-xl p-2">
                                <Network size={18} className="text-emerald-500" />
                            </div>
                        </div>
                        <div className="mt-4">
                            <span className="text-3xl font-bold text-slate-900">
                                {relatedConcepts.length}
                                <span className="text-sm font-normal text-slate-400 ml-1">个</span>
                            </span>
                        </div>
                    </div>
                </div>
            </div>

            {detail.description && (
                <div className="rounded-2xl border border-slate-200/60 bg-white p-5 shadow-sm">
                    <h3 className="text-sm font-semibold text-slate-900 mb-2">板块简介</h3>
                    <p className="text-sm text-slate-600">{detail.description}</p>
                </div>
            )}

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
                        <BarChart2 size={16} />
                        指数走势
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
                        成分股 ({detail.constituent_count})
                    </div>
                </button>
                <button
                    onClick={() => setActiveTab('related')}
                    className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                        activeTab === 'related'
                            ? 'border-primary text-primary'
                            : 'border-transparent text-slate-500 hover:text-slate-700'
                    }`}
                >
                    <div className="flex items-center gap-2">
                        <Network size={16} />
                        关联概念
                    </div>
                </button>
            </div>

            {activeTab === 'kline' && (
                <div className="rounded-2xl border border-slate-200/60 bg-white p-6 shadow-sm">
                    <div className="mb-4">
                        <h3 className="text-lg font-bold text-slate-900">{detail.name} 指数</h3>
                        <p className="text-xs text-slate-400 mt-1">基于成分股等权收益率合成</p>
                    </div>
                    {detail.index_series && detail.index_series.length > 0 ? (
                        <ReactECharts option={klineOption} style={{ height: 500 }} notMerge={true} />
                    ) : (
                        <div className="h-[500px] flex items-center justify-center text-slate-400">
                            暂无指数数据
                        </div>
                    )}
                </div>
            )}

            {activeTab === 'constituents' && (
                <div className="rounded-2xl border border-slate-200/60 bg-white shadow-sm overflow-hidden">
                    <div className="p-4 border-b border-slate-100">
                        <h3 className="text-lg font-bold text-slate-900">成分股列表</h3>
                        <p className="text-xs text-slate-400 mt-1">按当日涨跌幅排序</p>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead className="bg-slate-50/80">
                                <tr>
                                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">股票</th>
                                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">所属行业</th>
                                    <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wider">最新价</th>
                                    <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wider">涨跌幅</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                                {detail.constituents.map((item) => (
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
                                {detail.constituents.length === 0 && (
                                    <tr>
                                        <td colSpan={4} className="px-4 py-12 text-center text-slate-400">
                                            暂无成分股数据
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {activeTab === 'related' && (
                <div className="grid grid-cols-2 gap-6">
                    <div className="rounded-2xl border border-slate-200/60 bg-white p-6 shadow-sm">
                        <h3 className="text-lg font-bold text-slate-900 mb-2">关联概念图谱</h3>
                        <p className="text-xs text-slate-400 mb-4">基于共同成分股数量计算关联度</p>
                        {relatedConcepts.length > 0 ? (
                            <ReactECharts option={relatedGraphOption} style={{ height: 400 }} />
                        ) : (
                            <div className="h-[400px] flex items-center justify-center text-slate-400">
                                暂无关联概念
                            </div>
                        )}
                    </div>

                    <div className="rounded-2xl border border-slate-200/60 bg-white shadow-sm overflow-hidden">
                        <div className="p-4 border-b border-slate-100">
                            <h3 className="text-lg font-bold text-slate-900">关联概念列表</h3>
                            <p className="text-xs text-slate-400 mt-1">按重叠成分股数排序</p>
                        </div>
                        <div className="overflow-y-auto max-h-[480px]">
                            {relatedConcepts.map((item) => (
                                <Link
                                    key={item.code}
                                    to={`/concept/${item.code}`}
                                    className="flex items-center justify-between px-4 py-3 hover:bg-slate-50/50 transition-colors border-b border-slate-50 last:border-b-0"
                                >
                                    <div className="flex items-center gap-3">
                                        <div className="h-8 w-8 rounded-lg bg-slate-100 flex items-center justify-center">
                                            <Layers size={14} className="text-slate-500" />
                                        </div>
                                        <div>
                                            <p className="text-sm font-semibold text-slate-900">{item.name}</p>
                                            <p className="text-xs text-slate-400">
                                                重叠 {item.overlap_count} 只 · 共 {item.constituent_count} 只
                                            </p>
                                        </div>
                                    </div>
                                    <span className={`text-sm font-semibold ${getChangeColor(item.daily_change)}`}>
                                        {formatChange(item.daily_change)}
                                    </span>
                                </Link>
                            ))}
                            {relatedConcepts.length === 0 && (
                                <div className="px-4 py-12 text-center text-slate-400">
                                    暂无关联概念
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
