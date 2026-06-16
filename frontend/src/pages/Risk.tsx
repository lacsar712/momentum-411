import { useEffect, useMemo, useState } from 'react'
import ReactECharts from 'echarts-for-react'
import Loading from '../components/Loading'
import { api } from '../lib/api'
import { useToast } from '../components/Toast'
import DatePicker from '../components/DatePicker'
import Select from '../components/Select'
import MultiSelect from '../components/MultiSelect'
import {
    AlertTriangle,
    BarChart3,
    Activity,
    TrendingUp,
    ChevronUp,
    ChevronDown,
    ShieldAlert,
    Info,
    LineChart as LineChartIcon,
    PieChart,
} from 'lucide-react'

interface StockOption {
    symbol: string
    name: string
}

interface IndexOption {
    code: string
    name: string
    index_type: string
}

interface VarItem {
    symbol: string
    name: string
    data_points: number
    sufficient_data: boolean
    var_historical_95?: number | null
    var_parametric_95?: number | null
    var_historical_99?: number | null
    var_parametric_99?: number | null
    [key: string]: any
}

interface BetaItem {
    symbol: string
    name: string
    beta: number | null
    alpha: number | null
    r_squared: number | null
    p_value: number | null
    data_points: number
    sufficient_data: boolean
}

interface CorrelationData {
    symbols: string[]
    symbol_names: Record<string, string>
    matrix: number[][]
    data_points: Record<string, number>
    sufficient_data: Record<string, boolean>
}

interface MetricsItem {
    symbol: string
    name: string
    data_points: number
    sufficient_data: boolean
    annual_volatility: number | null
    max_drawdown: number | null
    total_return: number | null
    sharpe_ratio: number | null
    sortino_ratio: number | null
    calmar_ratio: number | null
}

interface RollingBetaData {
    dates: string[]
    items: Record<string, {
        name: string
        series: (number | null)[]
        sufficient_data: boolean
        message?: string
    }>
}

interface AllRiskResponse {
    var: {
        items: VarItem[]
        confidence_levels: number[]
        holding_period: number
        start_date: string
        end_date: string
    }
    beta_alpha: {
        items: BetaItem[]
        benchmark_code: string
        benchmark_name: string
    }
    correlation: CorrelationData
    metrics: {
        items: MetricsItem[]
    }
    rolling_beta: RollingBetaData
}

const BENCHMARK_OPTIONS = [
    { value: '000300', label: '沪深300 (000300)' },
    { value: '000905', label: '中证500 (000905)' },
    { value: '399006', label: '创业板指 (399006)' },
    { value: '000001', label: '上证指数 (000001)' },
    { value: '000016', label: '上证50 (000016)' },
    { value: '000852', label: '中证1000 (000852)' },
]

const CONFIDENCE_OPTIONS = [
    { value: 0.95, label: '95%' },
    { value: 0.99, label: '99%' },
]

const HOLDING_OPTIONS = [
    { value: 1, label: '1 天' },
    { value: 5, label: '5 天 (周)' },
    { value: 22, label: '22 天 (月)' },
    { value: 66, label: '66 天 (季)' },
    { value: 252, label: '252 天 (年)' },
]

const CHART_COLORS = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316']

export default function Risk() {
    const { pushToast } = useToast()

    const [loading, setLoading] = useState(false)
    const [allStocks, setAllStocks] = useState<StockOption[]>([])
    const [allIndices, setAllIndices] = useState<IndexOption[]>([])

    const today = new Date()
    const oneYearAgo = new Date()
    oneYearAgo.setFullYear(today.getFullYear() - 1)

    const [selectedSymbols, setSelectedSymbols] = useState<string[]>([])
    const [startDate, setStartDate] = useState(oneYearAgo.toISOString().split('T')[0])
    const [endDate, setEndDate] = useState(today.toISOString().split('T')[0])
    const [benchmarkCode, setBenchmarkCode] = useState('000300')
    const [confidence95, setConfidence95] = useState(true)
    const [confidence99, setConfidence99] = useState(true)
    const [holdingPeriod, setHoldingPeriod] = useState(1)

    const [result, setResult] = useState<AllRiskResponse | null>(null)

    const [metricsSortBy, setMetricsSortBy] = useState<string>('annual_volatility')
    const [metricsSortOrder, setMetricsSortOrder] = useState<'asc' | 'desc'>('asc')
    const [betaSortBy, setBetaSortBy] = useState<string>('beta')
    const [betaSortOrder, setBetaSortOrder] = useState<'asc' | 'desc'>('asc')

    useEffect(() => {
        api.get<{ items: StockOption[] }>('/stocks', { params: { limit: 10000 } })
            .then(res => setAllStocks(res.data.items || []))
            .catch(() => {})

        api.get<{ items: IndexOption[] }>('/index/list', { params: { limit: 100 } })
            .then(res => setAllIndices(res.data.items || []))
            .catch(() => {})
    }, [])

    const handleSymbolsChange = (symbols: string[]) => {
        setSelectedSymbols(symbols)
    }

    const runAnalysis = () => {
        if (selectedSymbols.length === 0) {
            pushToast('请至少选择一只股票', 'error')
            return
        }
        if (!startDate || !endDate) {
            pushToast('请选择日期范围', 'error')
            return
        }
        if (startDate > endDate) {
            pushToast('开始日期不能晚于结束日期', 'error')
            return
        }
        const levels: number[] = []
        if (confidence95) levels.push(0.95)
        if (confidence99) levels.push(0.99)
        if (levels.length === 0) {
            pushToast('请至少选择一个置信度', 'error')
            return
        }

        setLoading(true)
        api.post('/risk/all', {
            symbols: selectedSymbols,
            start_date: startDate,
            end_date: endDate,
            benchmark_code: benchmarkCode,
            confidence_levels: levels,
            holding_period: holdingPeriod,
            rolling_window: 60,
        })
            .then(res => {
                setResult(res.data)
                pushToast('风险指标计算完成', 'success')
            })
            .catch((err: any) => {
                const msg = err.response?.data?.detail || '计算失败，请检查数据是否充足'
                pushToast(msg, 'error')
            })
            .finally(() => setLoading(false))
    }

    const varHeatmapOption = useMemo(() => {
        if (!result || !result.var.items || result.var.items.length === 0) return {}
        const items = result.var.items
        const levels = result.var.confidence_levels || [0.95, 0.99]
        const methods = ['historical', 'parametric']

        const yLabels = items.map(i => `${i.name} (${i.symbol})`)
        const xLabels: string[] = []
        for (const l of levels) {
            for (const m of methods) {
                const methodName = m === 'historical' ? '历史法' : '参数法'
                xLabels.push(`${methodName} ${Math.round(l * 100)}%`)
            }
        }

        const data: [number, number, number][] = []
        items.forEach((item, rowIdx) => {
            let colIdx = 0
            for (const l of levels) {
                for (const m of methods) {
                    const key = `var_${m}_${Math.round(l * 100)}`
                    const val = item[key]
                    if (val !== null && val !== undefined) {
                        data.push([colIdx, rowIdx, Number(val.toFixed(2))])
                    }
                    colIdx++
                }
            }
        })

        const allVals = data.map(d => d[2]).filter(v => v !== undefined)
        const minVal = allVals.length ? Math.min(...allVals) : 0
        const maxVal = allVals.length ? Math.max(...allVals) : 0

        return {
            tooltip: {
                position: 'top',
                formatter: (p: any) => {
                    const col = p.data[0]
                    const row = p.data[1]
                    const val = p.data[2]
                    return `<div class="text-sm">
                        <div class="font-medium">${yLabels[row]}</div>
                        <div class="text-muted-foreground">${xLabels[col]}</div>
                        <div class="font-bold text-red-500 mt-1">VaR = ${val}%</div>
                    </div>`
                }
            },
            grid: { left: '20%', right: '10%', top: '5%', bottom: '15%' },
            xAxis: {
                type: 'category',
                data: xLabels,
                axisLabel: { rotate: 30, fontSize: 10 },
                splitArea: { show: true },
            },
            yAxis: {
                type: 'category',
                data: yLabels,
                axisLabel: { fontSize: 11 },
                splitArea: { show: true },
            },
            visualMap: {
                min: minVal,
                max: maxVal,
                calculable: true,
                orient: 'horizontal',
                left: 'center',
                bottom: '0%',
                inRange: {
                    color: ['#10b981', '#fbbf24', '#ef4444'],
                },
                text: ['风险高', '风险低'],
                textStyle: { fontSize: 10 },
            },
            series: [{
                name: 'VaR',
                type: 'heatmap',
                data: data,
                label: {
                    show: true,
                    formatter: (p: any) => `${p.data[2]}%`,
                    fontSize: 10,
                    color: '#000',
                },
                emphasis: {
                    itemStyle: {
                        shadowBlur: 10,
                        shadowColor: 'rgba(0, 0, 0, 0.5)',
                    },
                },
            }],
        }
    }, [result])

    const correlationHeatmapOption = useMemo(() => {
        if (!result || !result.correlation || !result.correlation.matrix || result.correlation.matrix.length === 0) {
            return {}
        }
        const { symbols, symbol_names, matrix } = result.correlation
        if (symbols.length === 0) return {}

        const labels = symbols.map(s => `${symbol_names[s] || s} (${s})`)
        const data: [number, number, number][] = []
        matrix.forEach((row, i) => {
            row.forEach((val, j) => {
                if (val !== null && val !== undefined) {
                    data.push([j, i, Number(val.toFixed(2))])
                }
            })
        })

        return {
            tooltip: {
                position: 'top',
                formatter: (p: any) => {
                    const col = p.data[0]
                    const row = p.data[1]
                    const val = p.data[2]
                    const sign = val >= 0 ? '正相关' : '负相关'
                    const strength = Math.abs(val) > 0.7 ? '强' : Math.abs(val) > 0.3 ? '中' : '弱'
                    return `<div class="text-sm">
                        <div class="font-medium">${labels[row]} × ${labels[col]}</div>
                        <div class="font-bold mt-1" style="color:${val >= 0 ? '#ef4444' : '#3b82f6'}">
                            相关系数 = ${val.toFixed(2)}
                        </div>
                        <div class="text-xs text-muted-foreground mt-1">${strength}${sign}</div>
                    </div>`
                }
            },
            grid: { left: '18%', right: '12%', top: '5%', bottom: '15%' },
            xAxis: {
                type: 'category',
                data: labels,
                axisLabel: { rotate: 45, fontSize: 10 },
                splitArea: { show: true },
            },
            yAxis: {
                type: 'category',
                data: labels,
                axisLabel: { fontSize: 11 },
                splitArea: { show: true },
            },
            visualMap: {
                min: -1,
                max: 1,
                calculable: true,
                orient: 'horizontal',
                left: 'center',
                bottom: '0%',
                inRange: {
                    color: ['#2563eb', '#dbeafe', '#fee2e2', '#dc2626'],
                },
                text: ['+1', '-1'],
                textStyle: { fontSize: 10 },
            },
            series: [{
                name: '相关系数',
                type: 'heatmap',
                data: data,
                label: {
                    show: true,
                    formatter: (p: any) => p.data[2].toFixed(2),
                    fontSize: 10,
                },
                emphasis: {
                    itemStyle: {
                        shadowBlur: 10,
                        shadowColor: 'rgba(0, 0, 0, 0.5)',
                    },
                },
            }],
        }
    }, [result])

    const rollingBetaChartOption = useMemo(() => {
        if (!result || !result.rolling_beta || !result.rolling_beta.dates) return {}
        const { dates, items } = result.rolling_beta
        if (!dates || dates.length === 0) return {}

        const series = Object.entries(items).map(([symbol, data], idx) => ({
            name: `${data.name} (${symbol})`,
            type: 'line',
            data: data.series,
            smooth: true,
            showSymbol: false,
            lineStyle: { width: 2, color: CHART_COLORS[idx % CHART_COLORS.length] },
            itemStyle: { color: CHART_COLORS[idx % CHART_COLORS.length] },
        })).filter((s: any) => s.data && s.data.length > 0)

        return {
            tooltip: { trigger: 'axis' },
            legend: {
                data: series.map((s: any) => s.name),
                top: 0,
                type: 'scroll',
            },
            grid: { left: '5%', right: '5%', top: '15%', bottom: '10%' },
            xAxis: {
                type: 'category',
                data: dates,
                axisLabel: {
                    rotate: 45,
                    fontSize: 10,
                    interval: Math.floor(dates.length / 10),
                },
                boundaryGap: false,
            },
            yAxis: {
                type: 'value',
                name: 'Beta',
                nameTextStyle: { fontSize: 11, color: '#64748b' },
                splitLine: { lineStyle: { type: 'dashed', opacity: 0.5 } },
            },
            series: series,
            dataZoom: [
                { type: 'inside', start: 0, end: 100 },
                { show: true, type: 'slider', bottom: 0, height: 18 },
            ],
        }
    }, [result])

    const handleMetricsSort = (field: string) => {
        if (metricsSortBy === field) {
            setMetricsSortOrder(metricsSortOrder === 'asc' ? 'desc' : 'asc')
        } else {
            setMetricsSortBy(field)
            setMetricsSortOrder('asc')
        }
    }

    const handleBetaSort = (field: string) => {
        if (betaSortBy === field) {
            setBetaSortOrder(betaSortOrder === 'asc' ? 'desc' : 'asc')
        } else {
            setBetaSortBy(field)
            setBetaSortOrder('asc')
        }
    }

    const sortedMetricsItems = useMemo(() => {
        if (!result?.metrics?.items) return []
        const sorted = [...result.metrics.items]
        const reverse = metricsSortOrder === 'desc'
        sorted.sort((a: any, b: any) => {
            const av = a[metricsSortBy] ?? (reverse ? -Infinity : Infinity)
            const bv = b[metricsSortBy] ?? (reverse ? -Infinity : Infinity)
            if (typeof av === 'number' && typeof bv === 'number') {
                return reverse ? bv - av : av - bv
            }
            return 0
        })
        return sorted
    }, [result, metricsSortBy, metricsSortOrder])

    const sortedBetaItems = useMemo(() => {
        if (!result?.beta_alpha?.items) return []
        const sorted = [...result.beta_alpha.items]
        const reverse = betaSortOrder === 'desc'
        sorted.sort((a: any, b: any) => {
            const av = a[betaSortBy] ?? (reverse ? -Infinity : Infinity)
            const bv = b[betaSortBy] ?? (reverse ? -Infinity : Infinity)
            if (typeof av === 'number' && typeof bv === 'number') {
                return reverse ? bv - av : av - bv
            }
            return 0
        })
        return sorted
    }, [result, betaSortBy, betaSortOrder])

    const anyInsufficientData = useMemo(() => {
        if (!result) return false
        const checks = [
            result.var?.items?.some((i: VarItem) => !i.sufficient_data),
            result.beta_alpha?.items?.some((i: BetaItem) => !i.sufficient_data),
            result.metrics?.items?.some((i: MetricsItem) => !i.sufficient_data),
            result.correlation && Object.values(result.correlation.sufficient_data || {}).some(v => !v),
        ]
        return checks.some(Boolean)
    }, [result])

    const DataInsufficientBanner = () => {
        if (!anyInsufficientData) return null
        return (
            <div className="rounded-xl border-2 border-amber-200 bg-amber-50 p-4 flex items-start gap-3">
                <AlertTriangle size={20} className="text-amber-600 shrink-0 mt-0.5" />
                <div className="flex-1">
                    <p className="text-sm font-semibold text-amber-900">部分标的数据不足（建议 ≥30 个有效交易日）</p>
                    <p className="text-xs text-amber-700 mt-1">
                        以下指标的统计可靠性可能下降：VaR、Beta/Alpha 回归、波动率、最大回撤等。建议扩大日期范围或选择数据更完整的股票。
                    </p>
                </div>
            </div>
        )
    }

    const MetricsSortHeader = ({ field, label }: { field: string; label: string }) => (
        <th
            className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider cursor-pointer hover:text-slate-700 select-none"
            onClick={() => handleMetricsSort(field)}
        >
            <div className="flex items-center gap-1.5">
                {label}
                <div className="flex flex-col ml-0.5">
                    <ChevronUp size={10} className={metricsSortBy === field && metricsSortOrder === 'asc' ? 'text-primary' : 'text-slate-300'} />
                    <ChevronDown size={10} className={metricsSortBy === field && metricsSortOrder === 'desc' ? 'text-primary' : 'text-slate-300'} />
                </div>
            </div>
        </th>
    )

    const BetaSortHeader = ({ field, label }: { field: string; label: string }) => (
        <th
            className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider cursor-pointer hover:text-slate-700 select-none"
            onClick={() => handleBetaSort(field)}
        >
            <div className="flex items-center gap-1.5">
                {label}
                <div className="flex flex-col ml-0.5">
                    <ChevronUp size={10} className={betaSortBy === field && betaSortOrder === 'asc' ? 'text-primary' : 'text-slate-300'} />
                    <ChevronDown size={10} className={betaSortBy === field && betaSortOrder === 'desc' ? 'text-primary' : 'text-slate-300'} />
                </div>
            </div>
        </th>
    )

    const formatPct = (val: number | null | undefined, suffix = '%') => {
        if (val === null || val === undefined || isNaN(val)) return '—'
        const sign = val > 0 ? '+' : ''
        return `${sign}${val.toFixed(2)}${suffix}`
    }

    const formatNum = (val: number | null | undefined, digits = 2) => {
        if (val === null || val === undefined || isNaN(val)) return '—'
        return val.toFixed(digits)
    }

    const getPValueLabel = (p: number | null | undefined) => {
        if (p === null || p === undefined || isNaN(p)) return { text: '—', color: 'text-slate-400' }
        if (p < 0.01) return { text: '***', color: 'text-emerald-600' }
        if (p < 0.05) return { text: '**', color: 'text-emerald-600' }
        if (p < 0.1) return { text: '*', color: 'text-amber-600' }
        return { text: '不显著', color: 'text-slate-400' }
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
                        <ShieldAlert size={24} className="text-primary" />
                        风险指标分析
                    </h2>
                    <p className="text-sm text-slate-500 mt-1">
                        专业风险度量：VaR、Beta/Alpha、相关性矩阵、年化波动率、最大回撤、滚动Beta
                    </p>
                </div>
                <button
                    onClick={runAnalysis}
                    disabled={loading}
                    className="rounded-xl bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 shadow-lg shadow-blue-500/20"
                >
                    {loading && (
                        <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                    )}
                    <Activity size={16} className={loading ? 'hidden' : ''} />
                    {loading ? '计算中...' : '开始分析'}
                </button>
            </div>

            <div className="rounded-2xl border border-slate-200/60 bg-white p-5 shadow-sm">
                <h3 className="text-sm font-semibold text-slate-900 mb-4 flex items-center gap-2">
                    <BarChart3 size={16} className="text-slate-500" />
                    参数配置
                </h3>
                <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-6 gap-4">
                    <div className="xl:col-span-2">
                        <label className="text-xs font-medium text-slate-500 mb-1.5 block">股票选择（多选）</label>
                        <MultiSelect
                            value={selectedSymbols}
                            onChange={handleSymbolsChange}
                            placeholder="选择股票..."
                            options={allStocks.map(s => ({ value: s.symbol, label: `${s.name} (${s.symbol})` }))}
                            maxDisplay={2}
                        />
                        <p className="mt-1 text-xs text-slate-400">建议选择 2~8 只股票便于对比分析</p>
                    </div>
                    <div>
                        <label className="text-xs font-medium text-slate-500 mb-1.5 block">开始日期</label>
                        <DatePicker value={startDate} onChange={setStartDate} />
                    </div>
                    <div>
                        <label className="text-xs font-medium text-slate-500 mb-1.5 block">结束日期</label>
                        <DatePicker value={endDate} onChange={setEndDate} />
                    </div>
                    <div>
                        <label className="text-xs font-medium text-slate-500 mb-1.5 block">基准指数</label>
                        <Select
                            value={benchmarkCode}
                            onChange={setBenchmarkCode}
                            placeholder="选择基准"
                            options={[
                                ...BENCHMARK_OPTIONS,
                                ...allIndices.slice(0, 10).map(i => ({ value: i.code, label: `${i.name} (${i.code})` })),
                            ]}
                        />
                    </div>
                    <div>
                        <label className="text-xs font-medium text-slate-500 mb-1.5 block">持有期 (VaR)</label>
                        <Select
                            value={String(holdingPeriod)}
                            onChange={(v) => setHoldingPeriod(Number(v))}
                            options={HOLDING_OPTIONS.map(o => ({ value: String(o.value), label: o.label }))}
                        />
                    </div>
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-4 pt-4 border-t border-slate-100">
                    <div>
                        <label className="text-xs font-medium text-slate-500 mb-2 block">置信度 (VaR)</label>
                        <div className="flex gap-3">
                            {CONFIDENCE_OPTIONS.map(opt => {
                                const checked = opt.value === 0.95 ? confidence95 : confidence99
                                const setter = opt.value === 0.95 ? setConfidence95 : setConfidence99
                                return (
                                    <label key={opt.value} className="flex items-center gap-2 cursor-pointer">
                                        <input
                                            type="checkbox"
                                            checked={checked}
                                            onChange={(e) => setter(e.target.checked)}
                                            className="h-4 w-4 rounded border-slate-300 text-primary focus:ring-primary"
                                        />
                                        <span className="text-sm text-slate-700">{opt.label}</span>
                                    </label>
                                )
                            })}
                        </div>
                    </div>
                    <div className="lg:col-span-2">
                        <label className="text-xs font-medium text-slate-500 mb-2 flex items-center gap-1">
                            <Info size={12} />
                            指标说明
                        </label>
                        <p className="text-xs text-slate-400 leading-relaxed">
                            VaR（在险价值）：给定置信度下持有期内的最大可能损失；
                            Beta：系统性风险系数（相对基准），Alpha：超额年化收益；
                            R²：拟合优度，p-value：Beta显著性（***&lt;0.01，**&lt;0.05，*&lt;0.1）；
                            滚动Beta：60日窗口动态Beta。
                        </p>
                    </div>
                </div>
            </div>

            {anyInsufficientData && <DataInsufficientBanner />}

            {loading ? (
                <div className="rounded-2xl border border-slate-200/60 bg-white p-12 shadow-sm">
                    <Loading />
                </div>
            ) : result ? (
                <div className="space-y-6">
                    <div className="rounded-2xl border border-slate-200/60 bg-white p-5 shadow-sm">
                        <div className="flex items-center justify-between mb-4">
                            <div>
                                <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                                    <ShieldAlert size={18} className="text-red-500" />
                                    VaR（在险价值）对比
                                </h3>
                                <p className="text-xs text-slate-400 mt-1">
                                    持有期 {result.var.holding_period} 天 · 统计区间 {result.var.start_date} ~ {result.var.end_date}
                                </p>
                            </div>
                        </div>
                        {result.var.items && result.var.items.length > 0 ? (
                            <div className="space-y-6">
                                <ReactECharts option={varHeatmapOption} style={{ height: Math.max(320, result.var.items.length * 60) }} notMerge={true} />

                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                    {result.var.items.map((item: VarItem, idx: number) => (
                                        <div
                                            key={item.symbol}
                                            className="rounded-xl border border-slate-200 bg-gradient-to-br from-slate-50/50 to-white p-4"
                                        >
                                            <div className="flex items-center justify-between mb-3">
                                                <div>
                                                    <p className="text-sm font-bold text-slate-900">{item.name}</p>
                                                    <p className="text-xs text-slate-400">
                                                        {item.symbol} · {item.data_points}个样本
                                                        {!item.sufficient_data && (
                                                            <span className="ml-1 text-amber-600">（数据不足）</span>
                                                        )}
                                                    </p>
                                                </div>
                                                <div
                                                    className="h-8 w-8 rounded-lg flex items-center justify-center"
                                                    style={{ backgroundColor: CHART_COLORS[idx % CHART_COLORS.length] + '15', color: CHART_COLORS[idx % CHART_COLORS.length] }}
                                                >
                                                    <BarChart3 size={16} />
                                                </div>
                                            </div>
                                            <div className="space-y-2">
                                                {(result.var.confidence_levels || [0.95, 0.99]).map((cl: number) => {
                                                    const clPct = Math.round(cl * 100)
                                                    const vh = item[`var_historical_${clPct}`] as number | null
                                                    const vp = item[`var_parametric_${clPct}`] as number | null
                                                    return (
                                                        <div key={cl}>
                                                            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
                                                                {clPct}% 置信度
                                                            </p>
                                                            <div className="grid grid-cols-2 gap-2">
                                                                <div className="rounded-lg bg-red-50 p-2">
                                                                    <p className="text-[10px] text-red-500">历史法</p>
                                                                    <p className="text-sm font-bold text-red-600">{formatPct(vh)}</p>
                                                                </div>
                                                                <div className="rounded-lg bg-orange-50 p-2">
                                                                    <p className="text-[10px] text-orange-500">参数法</p>
                                                                    <p className="text-sm font-bold text-orange-600">{formatPct(vp)}</p>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    )
                                                })}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ) : (
                            <EmptyState icon={<ShieldAlert />} title="暂无 VaR 数据" desc="请检查股票数据是否完整" />
                        )}
                    </div>

                    <div className="rounded-2xl border border-slate-200/60 bg-white shadow-sm overflow-hidden">
                        <div className="p-5 border-b border-slate-100">
                            <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                                <TrendingUp size={18} className="text-blue-500" />
                                Beta / Alpha 回归分析
                            </h3>
                            <p className="text-xs text-slate-400 mt-1">
                                基准：{result.beta_alpha.benchmark_name} ({result.beta_alpha.benchmark_code})
                                · R² 表示模型拟合优度，p-value 表示 Beta 统计显著性
                            </p>
                        </div>
                        {sortedBetaItems && sortedBetaItems.length > 0 ? (
                            <div className="overflow-x-auto">
                                <table className="w-full">
                                    <thead className="bg-slate-50/80">
                                        <tr>
                                            <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">股票</th>
                                            <BetaSortHeader field="beta" label="Beta" />
                                            <BetaSortHeader field="alpha" label="Alpha (年化)" />
                                            <BetaSortHeader field="r_squared" label="R² (拟合优度)" />
                                            <BetaSortHeader field="p_value" label="p-value" />
                                            <BetaSortHeader field="data_points" label="样本数" />
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-100">
                                        {sortedBetaItems.map((item: BetaItem) => {
                                            const pLabel = getPValueLabel(item.p_value)
                                            return (
                                                <tr key={item.symbol} className="hover:bg-slate-50/50 transition-colors">
                                                    <td className="px-4 py-4">
                                                        <div className="flex items-center gap-2">
                                                            <p className="text-sm font-semibold text-slate-900">{item.name}</p>
                                                            {!item.sufficient_data && (
                                                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-600 font-medium">
                                                                    数据不足
                                                                </span>
                                                            )}
                                                        </div>
                                                        <p className="text-xs text-slate-400">{item.symbol}</p>
                                                    </td>
                                                    <td className="px-4 py-4">
                                                        <span className={`text-sm font-bold ${
                                                            item.beta === null || item.beta === undefined ? 'text-slate-300' :
                                                            item.beta > 1 ? 'text-red-600' :
                                                            item.beta < 1 ? 'text-emerald-600' : 'text-slate-700'
                                                        }`}>
                                                            {formatNum(item.beta)}
                                                        </span>
                                                    </td>
                                                    <td className="px-4 py-4">
                                                        <span className={`text-sm font-semibold ${
                                                            item.alpha === null || item.alpha === undefined ? 'text-slate-300' :
                                                            item.alpha > 0 ? 'text-red-600' : 'text-emerald-600'
                                                        }`}>
                                                            {formatPct(item.alpha)}
                                                        </span>
                                                    </td>
                                                    <td className="px-4 py-4">
                                                        <div className="flex items-center gap-2">
                                                            <div className="w-16 h-2 rounded-full bg-slate-100 overflow-hidden">
                                                                <div
                                                                    className="h-full bg-gradient-to-r from-blue-400 to-blue-600"
                                                                    style={{ width: `${Math.min(100, Math.max(0, (item.r_squared ?? 0) * 100))}%` }}
                                                                />
                                                            </div>
                                                            <span className="text-sm font-medium text-slate-700">{formatNum(item.r_squared)}</span>
                                                        </div>
                                                    </td>
                                                    <td className="px-4 py-4">
                                                        <div className="flex items-center gap-2">
                                                            <span className="text-sm text-slate-600">{formatNum(item.p_value, 3)}</span>
                                                            <span className={`text-sm font-bold ${pLabel.color}`}>{pLabel.text}</span>
                                                        </div>
                                                    </td>
                                                    <td className="px-4 py-4 text-sm text-slate-600">{item.data_points}</td>
                                                </tr>
                                            )
                                        })}
                                    </tbody>
                                </table>
                            </div>
                        ) : (
                            <EmptyState icon={<TrendingUp />} title="暂无 Beta 数据" desc="请检查股票与基准数据是否完整" />
                        )}
                    </div>

                    <div className="rounded-2xl border border-slate-200/60 bg-white p-5 shadow-sm">
                        <div className="flex items-center justify-between mb-4">
                            <div>
                                <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                                    <PieChart size={18} className="text-purple-500" />
                                    相关性矩阵热力图
                                </h3>
                                <p className="text-xs text-slate-400 mt-1">
                                    皮尔逊相关系数：+1 完全正相关，-1 完全负相关，0 无相关
                                </p>
                            </div>
                        </div>
                        {result.correlation && result.correlation.matrix && result.correlation.matrix.length > 0 ? (
                            <ReactECharts
                                option={correlationHeatmapOption}
                                style={{ height: Math.max(400, result.correlation.symbols.length * 70) }}
                                notMerge={true}
                            />
                        ) : (
                            <EmptyState icon={<PieChart />} title="暂无相关性数据" desc="请选择至少2只有完整数据的股票" />
                        )}
                    </div>

                    <div className="rounded-2xl border border-slate-200/60 bg-white shadow-sm overflow-hidden">
                        <div className="p-5 border-b border-slate-100">
                            <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                                <Activity size={18} className="text-emerald-500" />
                                风险指标对比表
                            </h3>
                            <p className="text-xs text-slate-400 mt-1">
                                点击表头可排序。年化波动率：越低风险越低；夏普/索提诺/卡玛：越高风险调整收益越好
                            </p>
                        </div>
                        {sortedMetricsItems && sortedMetricsItems.length > 0 ? (
                            <div className="overflow-x-auto">
                                <table className="w-full">
                                    <thead className="bg-slate-50/80">
                                        <tr>
                                            <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">股票</th>
                                            <MetricsSortHeader field="annual_volatility" label="年化波动率" />
                                            <MetricsSortHeader field="max_drawdown" label="最大回撤" />
                                            <MetricsSortHeader field="total_return" label="累计收益" />
                                            <MetricsSortHeader field="sharpe_ratio" label="夏普比率" />
                                            <MetricsSortHeader field="sortino_ratio" label="索提诺比率" />
                                            <MetricsSortHeader field="calmar_ratio" label="卡玛比率" />
                                            <MetricsSortHeader field="data_points" label="样本数" />
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-100">
                                        {sortedMetricsItems.map((item: MetricsItem, idx: number) => (
                                            <tr key={item.symbol} className="hover:bg-slate-50/50 transition-colors">
                                                <td className="px-4 py-4">
                                                    <div className="flex items-center gap-3">
                                                        <div
                                                            className="h-2.5 w-2.5 rounded-full"
                                                            style={{ backgroundColor: CHART_COLORS[idx % CHART_COLORS.length] }}
                                                        />
                                                        <div>
                                                            <div className="flex items-center gap-2">
                                                                <p className="text-sm font-semibold text-slate-900">{item.name}</p>
                                                                {!item.sufficient_data && (
                                                                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-600 font-medium">
                                                                        数据不足
                                                                    </span>
                                                                )}
                                                            </div>
                                                            <p className="text-xs text-slate-400">{item.symbol}</p>
                                                        </div>
                                                    </div>
                                                </td>
                                                <td className="px-4 py-4">
                                                    <span className={`text-sm font-semibold ${
                                                        item.annual_volatility === null || item.annual_volatility === undefined ? 'text-slate-300' :
                                                        item.annual_volatility > 40 ? 'text-red-600' :
                                                        item.annual_volatility > 25 ? 'text-orange-600' : 'text-emerald-600'
                                                    }`}>
                                                        {formatPct(item.annual_volatility)}
                                                    </span>
                                                </td>
                                                <td className="px-4 py-4">
                                                    <span className={`text-sm font-semibold ${
                                                        item.max_drawdown === null || item.max_drawdown === undefined ? 'text-slate-300' :
                                                        item.max_drawdown < -40 ? 'text-red-600' :
                                                        item.max_drawdown < -20 ? 'text-orange-600' : 'text-amber-600'
                                                    }`}>
                                                        {formatPct(item.max_drawdown)}
                                                    </span>
                                                </td>
                                                <td className="px-4 py-4">
                                                    <span className={`text-sm font-semibold ${
                                                        item.total_return === null || item.total_return === undefined ? 'text-slate-300' :
                                                        item.total_return > 0 ? 'text-red-600' : 'text-emerald-600'
                                                    }`}>
                                                        {formatPct(item.total_return)}
                                                    </span>
                                                </td>
                                                <td className="px-4 py-4">
                                                    <span className={`text-sm font-bold ${
                                                        item.sharpe_ratio === null || item.sharpe_ratio === undefined ? 'text-slate-300' :
                                                        item.sharpe_ratio > 1 ? 'text-blue-600' :
                                                        item.sharpe_ratio > 0 ? 'text-slate-700' : 'text-slate-400'
                                                    }`}>
                                                        {formatNum(item.sharpe_ratio)}
                                                    </span>
                                                </td>
                                                <td className="px-4 py-4">
                                                    <span className={`text-sm font-bold ${
                                                        item.sortino_ratio === null || item.sortino_ratio === undefined ? 'text-slate-300' :
                                                        item.sortino_ratio > 1 ? 'text-purple-600' :
                                                        item.sortino_ratio > 0 ? 'text-slate-700' : 'text-slate-400'
                                                    }`}>
                                                        {formatNum(item.sortino_ratio)}
                                                    </span>
                                                </td>
                                                <td className="px-4 py-4">
                                                    <span className={`text-sm font-bold ${
                                                        item.calmar_ratio === null || item.calmar_ratio === undefined ? 'text-slate-300' :
                                                        item.calmar_ratio > 1 ? 'text-emerald-600' :
                                                        item.calmar_ratio > 0 ? 'text-slate-700' : 'text-slate-400'
                                                    }`}>
                                                        {formatNum(item.calmar_ratio)}
                                                    </span>
                                                </td>
                                                <td className="px-4 py-4 text-sm text-slate-600">{item.data_points}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        ) : (
                            <EmptyState icon={<Activity />} title="暂无风险指标数据" desc="请检查股票数据是否完整" />
                        )}
                    </div>

                    <div className="rounded-2xl border border-slate-200/60 bg-white p-5 shadow-sm">
                        <div className="flex items-center justify-between mb-4">
                            <div>
                                <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                                    <LineChartIcon size={18} className="text-indigo-500" />
                                    滚动 Beta 时间序列
                                </h3>
                                <p className="text-xs text-slate-400 mt-1">
                                    基准：{result.rolling_beta.benchmark_name} ({result.rolling_beta.benchmark_code})
                                    · 60 日滚动窗口
                                </p>
                            </div>
                        </div>
                        {result.rolling_beta && result.rolling_beta.dates && result.rolling_beta.dates.length > 0 ? (
                            <ReactECharts option={rollingBetaChartOption} style={{ height: 420 }} notMerge={true} />
                        ) : (
                            <EmptyState
                                icon={<LineChartIcon />}
                                title="暂无滚动 Beta 数据"
                                desc="有效数据不足60日，无法计算滚动Beta（建议扩大日期范围）"
                            />
                        )}
                    </div>
                </div>
            ) : (
                <div className="rounded-2xl border-2 border-dashed border-slate-200 bg-white p-16 shadow-sm text-center">
                    <ShieldAlert size={56} className="mx-auto text-slate-200 mb-4" />
                    <p className="text-slate-500 font-medium text-lg mb-2">配置参数并开始分析</p>
                    <p className="text-sm text-slate-400">
                        选择股票、日期范围、基准指数后，点击"开始分析"按钮
                    </p>
                    <div className="mt-6 inline-flex flex-col items-start gap-2 text-xs text-slate-400 text-left bg-slate-50 p-4 rounded-xl">
                        <p className="font-semibold text-slate-500">功能模块：</p>
                        <p>• VaR 卡片：双方法（历史/参数）+ 多置信度（95%/99%）对比</p>
                        <p>• Beta 表格：含 R² 拟合优度进度条 + p-value 星级显著性</p>
                        <p>• 相关性热力图：ECharts heatmap，蓝-白-红渐变配色</p>
                        <p>• 风险指标对比：波动率 / 回撤 / 夏普 / 索提诺 / 卡玛，支持排序</p>
                        <p>• 滚动 Beta 走势：60 日窗口动态 Beta 时间序列</p>
                    </div>
                </div>
            )}
        </div>
    )
}

function EmptyState({ icon, title, desc }: { icon: React.ReactNode; title: string; desc: string }) {
    return (
        <div className="py-12 text-center">
            <div className="inline-flex items-center justify-center h-14 w-14 rounded-2xl bg-slate-50 text-slate-300 mb-4">
                {icon}
            </div>
            <p className="text-slate-500 font-medium">{title}</p>
            <p className="text-xs text-slate-400 mt-1">{desc}</p>
        </div>
    )
}
