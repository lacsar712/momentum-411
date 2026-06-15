import { useEffect, useState, useMemo } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import ReactECharts from 'echarts-for-react'
import { GitCompare, Plus, X, TrendingUp, TrendingDown, Activity, Target, Calendar, ChevronDown, ChevronUp } from 'lucide-react'
import Loading from '../components/Loading'
import { api } from '../lib/api'
import DatePicker from '../components/DatePicker'
import Select from '../components/Select'

interface CompareSeries {
    code: string
    name: string
    index_type: 'index' | 'etf'
    series: { trade_date: string; value: number | null }[]
}

interface CompareStat {
    code: string
    name: string
    index_type: 'index' | 'etf'
    start_date: string | null
    end_date: string | null
    total_return: number
    max_drawdown: number
    volatility: number
    sharpe: number
    peak: number
    trough: number
}

interface IndexOption {
    id: number
    code: string
    name: string
    index_type: 'index' | 'etf'
}

const CHART_COLORS = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b']

export default function IndexCompare() {
    const navigate = useNavigate()
    const [searchParams] = useSearchParams()
    const [loading, setLoading] = useState(true)
    const [allIndices, setAllIndices] = useState<IndexOption[]>([])
    const [selectedCodes, setSelectedCodes] = useState<string[]>([])
    const [showSelector, setShowSelector] = useState(false)
    const [baseMethod, setBaseMethod] = useState<'first' | 'ytd' | 'y-1' | 'custom'>('first')
    const [customStartDate, setCustomStartDate] = useState('')
    const [seriesData, setSeriesData] = useState<CompareSeries[]>([])
    const [statsData, setStatsData] = useState<CompareStat[]>([])
    const [commonDates, setCommonDates] = useState<string[]>([])
    const [sortBy, setSortBy] = useState<string>('total_return')
    const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')

    useEffect(() => {
        api.get('/index/list', { params: { limit: 100 } })
            .then(res => {
                setAllIndices(res.data.items || [])
                const codesParam = searchParams.get('codes')
                if (codesParam) {
                    const codes = codesParam.split(',').slice(0, 4)
                    setSelectedCodes(codes)
                } else if (res.data.items && res.data.items.length >= 2) {
                    setSelectedCodes([res.data.items[0].code, res.data.items[1].code])
                }
            })
    }, [searchParams])

    useEffect(() => {
        if (baseMethod === 'custom' && !customStartDate) {
            const oneYearAgo = new Date()
            oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1)
            setCustomStartDate(oneYearAgo.toISOString().split('T')[0])
        }
    }, [baseMethod, customStartDate])

    useEffect(() => {
        if (selectedCodes.length < 2) {
            setSeriesData([])
            setStatsData([])
            setLoading(false)
            return
        }
        setLoading(true)
        const params: Record<string, any> = {
            codes: selectedCodes.join(','),
            base_method: baseMethod,
        }
        if (baseMethod === 'custom' && customStartDate) {
            params.start_date = customStartDate
        }
        api.get('/index/compare', { params })
            .then(res => {
                setSeriesData(res.data.items || [])
                setStatsData(res.data.stats || [])
                setCommonDates(res.data.dates || [])
            })
            .finally(() => setLoading(false))
    }, [selectedCodes, baseMethod, customStartDate])

    const addIndex = (code: string) => {
        if (selectedCodes.length >= 4) return
        if (selectedCodes.includes(code)) return
        setSelectedCodes([...selectedCodes, code])
        setShowSelector(false)
    }

    const removeIndex = (code: string) => {
        setSelectedCodes(selectedCodes.filter(c => c !== code))
    }

    const getIndexName = (code: string) => {
        return allIndices.find(i => i.code === code)?.name || code
    }

    const formatChange = (val: number) => {
        const sign = val >= 0 ? '+' : ''
        return `${sign}${val.toFixed(2)}%`
    }

    const getChangeColor = (val: number) => {
        if (val > 0) return 'text-red-500'
        if (val < 0) return 'text-emerald-500'
        return 'text-slate-400'
    }

    const getIndexColor = (index: number) => CHART_COLORS[index % CHART_COLORS.length]

    const chartOption = useMemo(() => {
        if (!seriesData || seriesData.length === 0 || commonDates.length === 0) return {}

        const series = seriesData.map((s, idx) => ({
            name: `${s.name} (${s.code})`,
            type: 'line',
            data: s.series.map(p => p.value),
            smooth: true,
            showSymbol: false,
            lineStyle: { width: 2.5, color: getIndexColor(idx) },
            itemStyle: { color: getIndexColor(idx) },
            areaStyle: {
                opacity: 0.05,
                color: getIndexColor(idx),
            },
        }))

        return {
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'cross' },
                formatter: (params: any) => {
                    if (!params || params.length === 0) return ''
                    const date = commonDates[params[0].dataIndex] || ''
                    let html = `<div class="font-medium mb-1">${date}</div>`
                    html += `<div class="text-xs space-y-1">`
                    for (const p of params) {
                        const val = p.data
                        const change = val !== null && val !== undefined ? (val - 100).toFixed(2) : '-'
                        const sign = val !== null && val !== undefined && val >= 100 ? '+' : ''
                        const color = val !== null && val !== undefined && val >= 100 ? '#ef4444' : (val < 100 ? '#10b981' : '#64748b')
                        html += `<div style="display:flex;align-items:center;gap:6px;">
                            <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};"></span>
                            <span>${p.seriesName}:</span>
                            <span style="color:${color};font-weight:600;">${val !== null && val !== undefined ? val.toFixed(2) : '-'} (${sign}${change}%)</span>
                        </div>`
                    }
                    html += `</div>`
                    return html
                }
            },
            legend: {
                data: series.map(s => s.name),
                top: 5,
                type: 'scroll',
            },
            grid: { left: '5%', right: '5%', bottom: '10%', top: '15%' },
            xAxis: {
                type: 'category',
                data: commonDates,
                axisLabel: {
                    rotate: 45,
                    fontSize: 10,
                    interval: Math.floor(commonDates.length / 12),
                },
                boundaryGap: false,
            },
            yAxis: {
                type: 'value',
                scale: true,
                name: '归一化净值 (基准=100)',
                nameTextStyle: { fontSize: 11, color: '#64748b' },
                axisLabel: {
                    formatter: (val: number) => {
                        const change = val - 100
                        const sign = change >= 0 ? '+' : ''
                        return `${val.toFixed(0)}\n${sign}${change.toFixed(0)}%`
                    },
                    fontSize: 10,
                },
                splitLine: { lineStyle: { type: 'dashed', opacity: 0.5 } },
            },
            dataZoom: [
                { type: 'inside', start: 0, end: 100 },
                { show: true, type: 'slider', bottom: 10, height: 18 },
            ],
            series,
        }
    }, [seriesData, commonDates])

    const sortedStats = useMemo(() => {
        const sorted = [...statsData]
        const reverse = sortOrder === 'desc'
        sorted.sort((a, b) => {
            const av = (a as any)[sortBy] ?? 0
            const bv = (b as any)[sortBy] ?? 0
            return reverse ? bv - av : av - bv
        })
        return sorted
    }, [statsData, sortBy, sortOrder])

    const handleSort = (field: string) => {
        if (sortBy === field) {
            setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
        } else {
            setSortBy(field)
            setSortOrder('desc')
        }
    }

    const SortHeader = ({ field, label }: { field: string; label: string }) => (
        <th
            className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider cursor-pointer hover:text-slate-700 select-none"
            onClick={() => handleSort(field)}
        >
            <div className="flex items-center gap-1.5">
                {label}
                <div className="flex flex-col ml-0.5">
                    <ChevronUp size={10} className={sortBy === field && sortOrder === 'asc' ? 'text-primary' : 'text-slate-300'} />
                    <ChevronDown size={10} className={sortBy === field && sortOrder === 'desc' ? 'text-primary' : 'text-slate-300'} />
                </div>
            </div>
        </th>
    )

    const availableToSelect = allIndices.filter(i => !selectedCodes.includes(i.code))

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold tracking-tight text-slate-900">指数与ETF对比</h2>
                    <p className="text-sm text-slate-500 mt-1">多标的归一化走势对比，支持2~4个同时分析</p>
                </div>
                <button
                    onClick={() => navigate('/index')}
                    className="h-10 px-4 rounded-xl border-2 border-slate-200 text-sm font-medium text-slate-600 hover:border-primary hover:text-primary transition-colors"
                >
                    返回列表
                </button>
            </div>

            <div className="rounded-2xl border border-slate-200/60 bg-white p-5 shadow-sm">
                <div className="flex items-center justify-between mb-4">
                    <h3 className="text-sm font-semibold text-slate-900">选择对比标的（2~4个）</h3>
                    <span className="text-xs text-slate-400">已选 {selectedCodes.length}/4</span>
                </div>
                <div className="flex flex-wrap items-center gap-2 mb-3">
                    {selectedCodes.map((code, idx) => (
                        <div
                            key={code}
                            className="flex items-center gap-2 pl-3 pr-2 py-1.5 rounded-xl border-2 text-sm font-medium transition-colors"
                            style={{
                                borderColor: getIndexColor(idx) + '40',
                                backgroundColor: getIndexColor(idx) + '08',
                                color: getIndexColor(idx),
                            }}
                        >
                            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: getIndexColor(idx) }} />
                            <span>{getIndexName(code)}</span>
                            <span className="text-xs opacity-60">{code}</span>
                            {selectedCodes.length > 2 && (
                                <button
                                    onClick={() => removeIndex(code)}
                                    className="h-5 w-5 rounded-md hover:bg-slate-200/50 flex items-center justify-center ml-1"
                                >
                                    <X size={12} />
                                </button>
                            )}
                        </div>
                    ))}
                    {selectedCodes.length < 4 && (
                        <div className="relative">
                            <button
                                onClick={() => setShowSelector(!showSelector)}
                                className="flex items-center gap-1.5 h-9 px-3 rounded-xl border-2 border-dashed border-slate-200 text-sm font-medium text-slate-500 hover:border-primary hover:text-primary transition-colors"
                            >
                                <Plus size={16} />
                                添加
                            </button>
                            {showSelector && availableToSelect.length > 0 && (
                                <div className="absolute top-full left-0 mt-1 z-50 w-72 max-h-80 overflow-y-auto rounded-xl border border-slate-200 bg-white shadow-lg">
                                    {availableToSelect.map(item => (
                                        <button
                                            key={item.code}
                                            onClick={() => addIndex(item.code)}
                                            className="w-full flex items-center justify-between px-3 py-2 hover:bg-slate-50 transition-colors text-left"
                                        >
                                            <div>
                                                <p className="text-sm font-medium text-slate-900">{item.name}</p>
                                                <p className="text-xs text-slate-400">{item.code}</p>
                                            </div>
                                            <span className={`text-xs px-1.5 py-0.5 rounded-md ${
                                                item.index_type === 'index'
                                                    ? 'bg-blue-50 text-blue-600'
                                                    : 'bg-purple-50 text-purple-600'
                                            }`}>
                                                {item.index_type === 'index' ? '指数' : 'ETF'}
                                            </span>
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                </div>

                <div className="flex flex-wrap items-center gap-4 pt-4 border-t border-slate-100">
                    <div className="flex items-center gap-2">
                        <Calendar size={16} className="text-slate-400" />
                        <span className="text-xs font-medium text-slate-500">起始基准:</span>
                        <div className="flex gap-1">
                            {[
                                { value: 'first', label: '首日' },
                                { value: 'ytd', label: '年初至今' },
                                { value: 'y-1', label: '近一年' },
                                { value: 'custom', label: '自定义' },
                            ].map(opt => (
                                <button
                                    key={opt.value}
                                    onClick={() => setBaseMethod(opt.value as any)}
                                    className={`h-8 px-3 rounded-lg text-xs font-medium transition-colors ${
                                        baseMethod === opt.value
                                            ? 'bg-primary text-white'
                                            : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                                    }`}
                                >
                                    {opt.label}
                                </button>
                            ))}
                        </div>
                    </div>
                    {baseMethod === 'custom' && (
                        <div className="flex items-center gap-2">
                            <span className="text-xs font-medium text-slate-500">开始日期:</span>
                            <DatePicker value={customStartDate} onChange={setCustomStartDate} />
                        </div>
                    )}
                </div>
            </div>

            {loading ? (
                <div className="rounded-2xl border border-slate-200/60 bg-white p-12 shadow-sm">
                    <Loading />
                </div>
            ) : seriesData.length > 0 ? (
                <>
                    <div className="rounded-2xl border border-slate-200/60 bg-white p-5 shadow-sm">
                        <div className="mb-4">
                            <h3 className="text-lg font-bold text-slate-900">归一化走势对比</h3>
                            <p className="text-xs text-slate-400 mt-1">
                                基准日 = {commonDates[0] || '-'}，基准净值 = 100
                            </p>
                        </div>
                        <ReactECharts option={chartOption} style={{ height: 480 }} notMerge={true} />
                    </div>

                    <div className="rounded-2xl border border-slate-200/60 bg-white shadow-sm overflow-hidden">
                        <div className="p-4 border-b border-slate-100">
                            <h3 className="text-lg font-bold text-slate-900">区间统计指标</h3>
                            <p className="text-xs text-slate-400 mt-1">
                                统计区间: {commonDates[0] || '-'} ~ {commonDates[commonDates.length - 1] || '-'}，共 {commonDates.length} 个交易日
                            </p>
                        </div>
                        <div className="overflow-x-auto">
                            <table className="w-full">
                                <thead className="bg-slate-50/80">
                                    <tr>
                                        <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">标的</th>
                                        <SortHeader field="total_return" label="区间收益" />
                                        <SortHeader field="max_drawdown" label="最大回撤" />
                                        <SortHeader field="volatility" label="年化波动率" />
                                        <SortHeader field="sharpe" label="夏普比率" />
                                        <SortHeader field="peak" label="区间最高" />
                                        <SortHeader field="trough" label="区间最低" />
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100">
                                    {sortedStats.map((stat, idx) => {
                                        const originalIdx = statsData.findIndex(s => s.code === stat.code)
                                        return (
                                            <tr key={stat.code} className="hover:bg-slate-50/50 transition-colors">
                                                <td className="px-4 py-4">
                                                    <div className="flex items-center gap-3">
                                                        <div
                                                            className="h-2.5 w-2.5 rounded-full"
                                                            style={{ backgroundColor: getIndexColor(originalIdx >= 0 ? originalIdx : idx) }}
                                                        />
                                                        <div>
                                                            <div className="flex items-center gap-2">
                                                                <p className="text-sm font-semibold text-slate-900">{stat.name}</p>
                                                                <span className={`text-xs px-1.5 py-0.5 rounded-md ${
                                                                    stat.index_type === 'index'
                                                                        ? 'bg-blue-50 text-blue-600'
                                                                        : 'bg-purple-50 text-purple-600'
                                                                }`}>
                                                                    {stat.index_type === 'index' ? '指数' : 'ETF'}
                                                                </span>
                                                            </div>
                                                            <p className="text-xs text-slate-400">{stat.code}</p>
                                                        </div>
                                                    </div>
                                                </td>
                                                <td className="px-4 py-4">
                                                    <div className="flex items-center gap-1.5">
                                                        {stat.total_return >= 0
                                                            ? <TrendingUp size={14} className="text-red-500" />
                                                            : <TrendingDown size={14} className="text-emerald-500" />
                                                        }
                                                        <span className={`text-sm font-semibold ${getChangeColor(stat.total_return)}`}>
                                                            {formatChange(stat.total_return)}
                                                        </span>
                                                    </div>
                                                </td>
                                                <td className="px-4 py-4">
                                                    <span className="text-sm font-semibold text-emerald-600">
                                                        {stat.max_drawdown.toFixed(2)}%
                                                    </span>
                                                </td>
                                                <td className="px-4 py-4">
                                                    <div className="flex items-center gap-1.5">
                                                        <Activity size={14} className="text-slate-400" />
                                                        <span className="text-sm font-medium text-slate-700">
                                                            {stat.volatility.toFixed(2)}%
                                                        </span>
                                                    </div>
                                                </td>
                                                <td className="px-4 py-4">
                                                    <span className={`text-sm font-semibold ${
                                                        stat.sharpe > 1 ? 'text-blue-600' :
                                                        stat.sharpe > 0 ? 'text-slate-700' : 'text-slate-400'
                                                    }`}>
                                                        {stat.sharpe.toFixed(2)}
                                                    </span>
                                                </td>
                                                <td className="px-4 py-4">
                                                    <span className={`text-sm font-medium ${getChangeColor(stat.peak)}`}>
                                                        <Target size={12} className="inline mr-1" />
                                                        {formatChange(stat.peak)}
                                                    </span>
                                                </td>
                                                <td className="px-4 py-4">
                                                    <span className={`text-sm font-medium ${getChangeColor(stat.trough)}`}>
                                                        <Target size={12} className="inline mr-1" />
                                                        {formatChange(stat.trough)}
                                                    </span>
                                                </td>
                                            </tr>
                                        )
                                    })}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-5">
                        {seriesData.map((s, idx) => (
                            <div
                                key={s.code}
                                className="rounded-2xl border border-slate-200/60 bg-white p-5 shadow-sm"
                            >
                                <div className="flex items-center justify-between mb-4">
                                    <div className="flex items-center gap-2">
                                        <div
                                            className="h-3 w-3 rounded-full"
                                            style={{ backgroundColor: getIndexColor(idx) }}
                                        />
                                        <h4 className="text-sm font-bold text-slate-900">{s.name}</h4>
                                        <span className="text-xs text-slate-400">{s.code}</span>
                                    </div>
                                    <button
                                        onClick={() => navigate(`/index/${s.code}`)}
                                        className="text-xs font-medium text-primary hover:text-primary/80"
                                    >
                                        查看详情 →
                                    </button>
                                </div>
                                {(() => {
                                    const stat = statsData.find(x => x.code === s.code)
                                    if (!stat) return null
                                    return (
                                        <div className="grid grid-cols-3 gap-3">
                                            <div className="rounded-xl bg-slate-50/80 p-3">
                                                <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wider">累计收益</p>
                                                <p className={`text-lg font-bold mt-1 ${getChangeColor(stat.total_return)}`}>
                                                    {formatChange(stat.total_return)}
                                                </p>
                                            </div>
                                            <div className="rounded-xl bg-slate-50/80 p-3">
                                                <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wider">最大回撤</p>
                                                <p className="text-lg font-bold mt-1 text-emerald-600">
                                                    {stat.max_drawdown.toFixed(2)}%
                                                </p>
                                            </div>
                                            <div className="rounded-xl bg-slate-50/80 p-3">
                                                <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wider">夏普比率</p>
                                                <p className={`text-lg font-bold mt-1 ${
                                                    stat.sharpe > 1 ? 'text-blue-600' : 'text-slate-700'
                                                }`}>
                                                    {stat.sharpe.toFixed(2)}
                                                </p>
                                            </div>
                                        </div>
                                    )
                                })()}
                            </div>
                        ))}
                    </div>
                </>
            ) : (
                <div className="rounded-2xl border border-slate-200/60 bg-white p-12 shadow-sm text-center">
                    <GitCompare size={48} className="mx-auto text-slate-300 mb-4" />
                    <p className="text-slate-500 font-medium">请至少选择2个标的进行对比</p>
                    <p className="text-xs text-slate-400 mt-1">点击上方"添加"按钮选择指数或ETF</p>
                </div>
            )}
        </div>
    )
}
