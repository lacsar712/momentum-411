import { useState, useEffect, useMemo, useCallback } from 'react'
import ReactECharts from 'echarts-for-react'
import {
    Plus, Copy, Trash2, AlertTriangle, TrendingUp, TrendingDown,
    Edit3, Save, X, Search, RefreshCw, PieChart, BarChart3,
    Activity, Target, AlertCircle, CheckCircle
} from 'lucide-react'
import { api } from '../lib/api'
import Loading from '../components/Loading'
import Modal from '../components/Modal'
import Select from '../components/Select'
import { useToast } from '../components/Toast'

interface Portfolio {
    id: number
    user_id: number
    name: string
    description?: string
    benchmark_code: string
    rebalance_frequency: string
    created_at: string
    updated_at: string
    holdings: Holding[]
}

interface Holding {
    id?: number
    symbol: string
    name?: string
    target_weight: number
    current_weight?: number
    weight_deviation?: number
    latest_price?: number
    daily_change?: number
}

interface NavPoint {
    trade_date: string
    portfolio_nav: number
    benchmark_nav: number
}

interface PortfolioMetrics {
    annual_return: number
    benchmark_annual_return: number
    excess_return: number
    max_drawdown: number
    benchmark_max_drawdown: number
    sharpe_ratio: number
    information_ratio: number
    correlation: number
    total_return: number
    benchmark_total_return: number
    volatility: number
    benchmark_volatility: number
}

interface RebalanceSuggestion {
    symbol: string
    name?: string
    target_weight: number
    current_weight: number
    deviation: number
    action: string
    suggested_amount: number
    latest_price?: number
}

interface RebalanceResponse {
    threshold: number
    total_deviation: number
    needs_rebalance: boolean
    suggestions: RebalanceSuggestion[]
    portfolio_value: number
}

const REBALANCE_OPTIONS = [
    { value: 'daily', label: '日频' },
    { value: 'weekly', label: '周频' },
    { value: 'monthly', label: '月频' },
    { value: 'quarterly', label: '季频' },
    { value: 'yearly', label: '年频' },
]

const BENCHMARK_OPTIONS = [
    { value: '000300', label: '沪深300 (000300)' },
    { value: '000905', label: '中证500 (000905)' },
    { value: '000852', label: '中证1000 (000852)' },
    { value: '399001', label: '深证成指 (399001)' },
    { value: '000001', label: '上证指数 (000001)' },
    { value: '399006', label: '创业板指 (399006)' },
]

const formatPercent = (v: number | undefined, digits = 2) =>
    v === undefined || v === null ? '--' : `${(v * 100).toFixed(digits)}%`

const formatCurrency = (v: number | undefined) =>
    v === undefined || v === null ? '--'
        : v >= 1e8 ? `${(v / 1e8).toFixed(2)}亿`
        : v >= 1e4 ? `${(v / 1e4).toFixed(2)}万`
        : v.toFixed(2)

const colorForDeviation = (dev: number | undefined) => {
    if (dev === undefined || dev === null) return 'text-slate-500'
    const abs = Math.abs(dev)
    if (abs >= 10) return 'text-red-600 font-semibold'
    if (abs >= 5) return 'text-orange-500 font-medium'
    if (abs >= 2) return 'text-amber-500'
    return 'text-emerald-600'
}

export default function PortfolioMgmt() {
    const { pushToast } = useToast()
    const toast = {
        success: (m: string) => pushToast(m, 'success'),
        error: (m: string) => pushToast(m, 'error'),
    }
    const [portfolios, setPortfolios] = useState<Portfolio[]>([])
    const [selectedId, setSelectedId] = useState<number | null>(null)
    const [loading, setLoading] = useState(true)
    const [detailLoading, setDetailLoading] = useState(false)

    const [navData, setNavData] = useState<NavPoint[]>([])
    const [metrics, setMetrics] = useState<PortfolioMetrics | null>(null)
    const [rebalance, setRebalance] = useState<RebalanceResponse | null>(null)

    const [showCreateModal, setShowCreateModal] = useState(false)
    const [showCopyModal, setShowCopyModal] = useState(false)
    const [showHoldingEditModal, setShowHoldingEditModal] = useState(false)
    const [showAddHoldingModal, setShowAddHoldingModal] = useState(false)
    const [editingHolding, setEditingHolding] = useState<Holding | null>(null)

    const [newPortfolio, setNewPortfolio] = useState({
        name: '', description: '', benchmark_code: '000300', rebalance_frequency: 'monthly'
    })
    const [copyName, setCopyName] = useState('')
    const [newHolding, setNewHolding] = useState({ symbol: '', target_weight: 20, name: '' })
    const [stockSearch, setStockSearch] = useState('')
    const [stockResults, setStockResults] = useState<any[]>([])
    const [rebalanceThreshold, setRebalanceThreshold] = useState(5)
    const [portfolioValue, setPortfolioValue] = useState(1000000)

    const selected = useMemo(() => portfolios.find(p => p.id === selectedId) || null, [portfolios, selectedId])

    const loadPortfolios = useCallback(async () => {
        setLoading(true)
        try {
            const res = await api.get('/portfolio')
            const list: Portfolio[] = res.data.items || []
            setPortfolios(list)
            if (!selectedId && list.length > 0) {
                setSelectedId(list[0].id)
            }
        } catch (e: any) {
            toast.error(e.response?.data?.detail || '加载组合列表失败')
        } finally {
            setLoading(false)
        }
    }, [selectedId])

    const loadDetail = useCallback(async (id: number) => {
        setDetailLoading(true)
        try {
            const [detailRes, navRes, metricsRes, rebalRes] = await Promise.all([
                api.get(`/portfolio/${id}`),
                api.get(`/portfolio/${id}/nav`),
                api.get(`/portfolio/${id}/metrics`),
                api.get(`/portfolio/${id}/rebalance`, { params: { threshold: rebalanceThreshold, portfolio_value: portfolioValue } }),
            ])
            const updatedPortfolios = portfolios.map(p =>
                p.id === id ? { ...p, ...detailRes.data, holdings: detailRes.data.holdings || [] } : p
            )
            setPortfolios(updatedPortfolios)
            setNavData(navRes.data.data || [])
            setMetrics(metricsRes.data)
            setRebalance(rebalRes.data)
        } catch (e: any) {
            toast.error(e.response?.data?.detail || '加载组合详情失败')
        } finally {
            setDetailLoading(false)
        }
    }, [portfolios, rebalanceThreshold, portfolioValue])

    useEffect(() => {
        loadPortfolios()
    }, [loadPortfolios])

    useEffect(() => {
        if (selectedId) {
            loadDetail(selectedId)
        }
    }, [selectedId, loadDetail])

    const handleCreate = async () => {
        if (!newPortfolio.name.trim()) {
            toast.error('请输入组合名称')
            return
        }
        try {
            const res = await api.post('/portfolio', newPortfolio)
            setPortfolios(prev => [...prev, res.data])
            setSelectedId(res.data.id)
            setShowCreateModal(false)
            setNewPortfolio({ name: '', description: '', benchmark_code: '000300', rebalance_frequency: 'monthly' })
            toast.success('组合创建成功')
        } catch (e: any) {
            toast.error(e.response?.data?.detail || '创建失败')
        }
    }

    const handleCopy = async () => {
        if (!selected || !copyName.trim()) {
            toast.error('请输入新组合名称')
            return
        }
        try {
            const res = await api.post(`/portfolio/${selected.id}/copy`, { new_name: copyName })
            setPortfolios(prev => [...prev, res.data])
            setSelectedId(res.data.id)
            setShowCopyModal(false)
            setCopyName('')
            toast.success('组合复制成功')
        } catch (e: any) {
            toast.error(e.response?.data?.detail || '复制失败')
        }
    }

    const handleDelete = async (id: number) => {
        if (!confirm('确定要删除此组合吗？')) return
        try {
            await api.delete(`/portfolio/${id}`)
            const next = portfolios.filter(p => p.id !== id)
            setPortfolios(next)
            if (selectedId === id) {
                setSelectedId(next.length ? next[0].id : null)
            }
            toast.success('删除成功')
        } catch (e: any) {
            toast.error(e.response?.data?.detail || '删除失败')
        }
    }

    const searchStock = async (kw: string) => {
        setStockSearch(kw)
        if (kw.length < 1) {
            setStockResults([])
            return
        }
        try {
            const res = await api.get('/stocks/query', { params: { keyword: kw, limit: 20 } })
            setStockResults(res.data.items || [])
        } catch {
            setStockResults([])
        }
    }

    const handleAddHolding = async () => {
        if (!selected) return
        if (!newHolding.symbol.trim()) {
            toast.error('请选择股票')
            return
        }
        try {
            await api.post(`/portfolio/${selected.id}/holdings`, {
                symbol: newHolding.symbol,
                target_weight: Number(newHolding.target_weight),
            })
            setShowAddHoldingModal(false)
            setNewHolding({ symbol: '', target_weight: 20, name: '' })
            setStockResults([])
            setStockSearch('')
            toast.success('添加成功')
            loadDetail(selected.id)
        } catch (e: any) {
            toast.error(e.response?.data?.detail || '添加失败')
        }
    }

    const handleUpdateHolding = async () => {
        if (!selected || !editingHolding) return
        try {
            await api.patch(`/portfolio/${selected.id}/holdings/${editingHolding.id}`, {
                target_weight: Number(editingHolding.target_weight),
            })
            setShowHoldingEditModal(false)
            setEditingHolding(null)
            toast.success('权重更新成功')
            loadDetail(selected.id)
        } catch (e: any) {
            toast.error(e.response?.data?.detail || '更新失败')
        }
    }

    const handleDeleteHolding = async (holdingId: number) => {
        if (!selected || !confirm('确定移除此持仓？')) return
        try {
            await api.delete(`/portfolio/${selected.id}/holdings/${holdingId}`)
            toast.success('已移除')
            loadDetail(selected.id)
        } catch (e: any) {
            toast.error(e.response?.data?.detail || '移除失败')
        }
    }

    const pieOption = useMemo(() => {
        const data = (selected?.holdings || []).map(h => ({
            name: `${h.name || h.symbol}`,
            value: h.target_weight,
            symbol: h.symbol,
        }))
        return {
            tooltip: {
                trigger: 'item',
                formatter: (p: any) => `${p.data.symbol} ${p.data.name}<br/>目标权重: ${p.data.value.toFixed(2)}%<br/>占比: ${p.percent}%`
            },
            legend: { bottom: '0%', left: 'center', icon: 'circle', type: 'scroll' },
            color: ['#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#06b6d4', '#ef4444', '#14b8a6', '#6366f1', '#f97316'],
            series: [{
                name: '权重',
                type: 'pie',
                radius: ['35%', '65%'],
                center: ['50%', '45%'],
                itemStyle: { borderRadius: 8, borderColor: '#fff', borderWidth: 2 },
                data,
                emphasis: {
                    label: { show: true, fontSize: 14, fontWeight: 'bold', formatter: '{b}\n{d}%' }
                },
                label: { show: false, position: 'center' }
            }]
        }
    }, [selected])

    const navOption = useMemo(() => {
        const dates = navData.map(d => d.trade_date)
        const pf = navData.map(d => +(d.portfolio_nav).toFixed(4))
        const bm = navData.map(d => +(d.benchmark_nav).toFixed(4))
        return {
            tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
            legend: { data: ['组合净值', '基准净值'], top: 0 },
            grid: { left: '3%', right: '4%', bottom: '3%', top: '15%', containLabel: true },
            xAxis: { type: 'category', boundaryGap: false, data: dates, axisLabel: { formatter: (v: string) => v.slice(5) } },
            yAxis: { type: 'value', scale: true, axisLabel: { formatter: '{value}' } },
            dataZoom: [{ type: 'inside', start: 0, end: 100 }, { type: 'slider', start: 0, end: 100, height: 16, bottom: 0 }],
            series: [
                {
                    name: '组合净值', type: 'line', data: pf, smooth: true, showSymbol: false,
                    lineStyle: { color: '#3b82f6', width: 2 },
                    itemStyle: { color: '#3b82f6' },
                    areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(59,130,246,0.2)' }, { offset: 1, color: 'rgba(59,130,246,0.02)' }] } }
                },
                {
                    name: '基准净值', type: 'line', data: bm, smooth: true, showSymbol: false,
                    lineStyle: { color: '#94a3b8', width: 2, type: 'dashed' },
                    itemStyle: { color: '#94a3b8' }
                }
            ]
        }
    }, [navData])

    const totalTargetWeight = useMemo(() =>
        (selected?.holdings || []).reduce((s, h) => s + h.target_weight, 0)
    , [selected])

    return (
        <div className="flex h-[calc(100vh-64px)] -mx-8 -my-6 overflow-hidden">
            {/* 左侧组合列表 */}
            <aside className="w-80 shrink-0 border-r border-slate-200/60 bg-slate-50/50 flex flex-col">
                <div className="p-4 border-b border-slate-200/60 bg-white">
                    <div className="flex items-center justify-between mb-3">
                        <div>
                            <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                                <PieChart size={18} className="text-primary" />
                                投资组合
                            </h2>
                            <p className="text-xs text-slate-400 mt-0.5">共 {portfolios.length} 个组合</p>
                        </div>
                        <button
                            onClick={() => setShowCreateModal(true)}
                            className="h-9 w-9 rounded-xl bg-primary text-white flex items-center justify-center hover:bg-primary/90 shadow-sm shadow-blue-200 transition-colors"
                            title="新建组合"
                        >
                            <Plus size={18} />
                        </button>
                    </div>
                </div>
                <div className="flex-1 overflow-y-auto p-3 space-y-2">
                    {loading ? (
                        <div className="p-8"><Loading /></div>
                    ) : portfolios.length === 0 ? (
                        <div className="p-8 text-center">
                            <div className="h-16 w-16 mx-auto mb-4 rounded-2xl bg-slate-100 flex items-center justify-center">
                                <PieChart size={28} className="text-slate-400" />
                            </div>
                            <p className="text-sm text-slate-500 mb-3">还没有组合</p>
                            <button
                                onClick={() => setShowCreateModal(true)}
                                className="text-xs font-medium text-primary hover:underline"
                            >
                                + 创建第一个组合
                            </button>
                        </div>
                    ) : (
                        portfolios.map(p => (
                            <div
                                key={p.id}
                                onClick={() => setSelectedId(p.id)}
                                className={`group relative rounded-xl p-3.5 border cursor-pointer transition-all ${
                                    selectedId === p.id
                                        ? 'bg-white border-primary/30 shadow-md shadow-blue-50 ring-1 ring-primary/10'
                                        : 'bg-white/60 border-slate-200/60 hover:bg-white hover:border-slate-200 hover:shadow-sm'
                                }`}
                            >
                                <div className="flex items-start justify-between gap-2">
                                    <div className="min-w-0 flex-1">
                                        <p className={`font-semibold truncate ${selectedId === p.id ? 'text-primary' : 'text-slate-800'}`}>
                                            {p.name}
                                        </p>
                                        {p.description && (
                                            <p className="text-xs text-slate-400 mt-1 line-clamp-1">{p.description}</p>
                                        )}
                                        <div className="flex items-center gap-3 mt-2 text-[10px] text-slate-400">
                                            <span className="inline-flex items-center gap-1">
                                                <Target size={10} />
                                                {p.holdings.length} 成分
                                            </span>
                                            <span className="inline-flex items-center gap-1">
                                                <RefreshCw size={10} />
                                                {REBALANCE_OPTIONS.find(o => o.value === p.rebalance_frequency)?.label || '月频'}
                                            </span>
                                        </div>
                                    </div>
                                    {selectedId === p.id && (
                                        <div className="h-2 w-2 rounded-full bg-primary shrink-0 mt-1.5" />
                                    )}
                                </div>
                                <div className="flex items-center gap-1 mt-3 pt-2 border-t border-slate-100 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <button
                                        onClick={(e) => { e.stopPropagation(); setShowCopyModal(true) }}
                                        className="flex-1 text-[10px] py-1.5 rounded-md text-slate-500 hover:text-primary hover:bg-primary/5 transition-colors"
                                        title="复制组合"
                                    >
                                        <Copy size={12} className="inline mr-1" />复制
                                    </button>
                                    <button
                                        onClick={(e) => { e.stopPropagation(); handleDelete(p.id) }}
                                        className="flex-1 text-[10px] py-1.5 rounded-md text-slate-500 hover:text-red-500 hover:bg-red-50 transition-colors"
                                        title="删除组合"
                                    >
                                        <Trash2 size={12} className="inline mr-1" />删除
                                    </button>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </aside>

            {/* 右侧详情 */}
            <main className="flex-1 overflow-y-auto bg-slate-50/30">
                {!selected ? (
                    <div className="h-full flex items-center justify-center">
                        <div className="text-center">
                            <div className="h-24 w-24 mx-auto mb-6 rounded-3xl bg-gradient-to-br from-blue-100 to-indigo-100 flex items-center justify-center">
                                <BarChart3 size={40} className="text-primary" />
                            </div>
                            <h3 className="text-xl font-bold text-slate-800 mb-2">选择或创建一个组合</h3>
                            <p className="text-sm text-slate-500">开始构建您的投资组合，跟踪收益与风险</p>
                        </div>
                    </div>
                ) : (
                    <div className="p-6 space-y-6">
                        {detailLoading && (
                            <div className="fixed inset-0 z-40 bg-white/30 backdrop-blur-sm flex items-center justify-center">
                                <Loading />
                            </div>
                        )}

                        {/* 顶部标题 + 操作栏 */}
                        <div className="flex items-start justify-between gap-4">
                            <div>
                                <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-3">
                                    {selected.name}
                                    <button
                                        onClick={() => loadDetail(selected.id)}
                                        className="h-8 w-8 rounded-lg bg-slate-100 text-slate-500 hover:bg-slate-200 hover:text-slate-700 flex items-center justify-center transition-colors"
                                        title="刷新"
                                    >
                                        <RefreshCw size={15} />
                                    </button>
                                </h1>
                                {selected.description && (
                                    <p className="text-sm text-slate-500 mt-1">{selected.description}</p>
                                )}
                                <div className="flex items-center gap-4 mt-2 text-xs text-slate-500">
                                    <span>基准: <b className="text-slate-700">{BENCHMARK_OPTIONS.find(o => o.value === selected.benchmark_code)?.label || selected.benchmark_code}</b></span>
                                    <span>再平衡: <b className="text-slate-700">{REBALANCE_OPTIONS.find(o => o.value === selected.rebalance_frequency)?.label || '月频'}</b></span>
                                    <span>创建于: {new Date(selected.created_at).toLocaleDateString()}</span>
                                </div>
                            </div>
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={() => setShowCopyModal(true)}
                                    className="h-9 px-4 rounded-xl border border-slate-200 bg-white text-slate-600 hover:border-primary/30 hover:text-primary transition-colors text-sm font-medium flex items-center gap-1.5"
                                >
                                    <Copy size={15} />复制
                                </button>
                                <button
                                    onClick={() => handleDelete(selected.id)}
                                    className="h-9 px-4 rounded-xl border border-red-100 bg-red-50 text-red-500 hover:border-red-200 hover:bg-red-100 transition-colors text-sm font-medium flex items-center gap-1.5"
                                >
                                    <Trash2 size={15} />删除
                                </button>
                            </div>
                        </div>

                        {/* 再平衡建议高亮提示区 */}
                        {rebalance && rebalance.needs_rebalance && (
                            <div className={`rounded-2xl border p-5 ${
                                rebalance.total_deviation >= 30
                                    ? 'border-red-200 bg-gradient-to-r from-red-50 to-orange-50'
                                    : 'border-amber-200 bg-gradient-to-r from-amber-50 to-yellow-50'
                            }`}>
                                <div className="flex items-start gap-4">
                                    <div className={`h-11 w-11 rounded-xl flex items-center justify-center shrink-0 ${
                                        rebalance.total_deviation >= 30 ? 'bg-red-100 text-red-600' : 'bg-amber-100 text-amber-600'
                                    }`}>
                                        <AlertTriangle size={22} />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <h3 className={`font-bold mb-1 ${rebalance.total_deviation >= 30 ? 'text-red-700' : 'text-amber-700'}`}>
                                            建议进行再平衡
                                        </h3>
                                        <p className="text-sm text-slate-600 mb-3">
                                            当前总偏离 <b className={rebalance.total_deviation >= 30 ? 'text-red-600' : 'text-amber-600'}>{rebalance.total_deviation.toFixed(2)}%</b>，
                                            阈值 {rebalance.threshold}%，共 {rebalance.suggestions.length} 只成分股需调整
                                        </p>
                                        <div className="grid grid-cols-2 md:grid-cols-3 gap-2.5">
                                            {rebalance.suggestions.slice(0, 6).map(s => (
                                                <div key={s.symbol} className="rounded-xl bg-white/70 backdrop-blur-sm border border-white px-3 py-2.5 shadow-sm">
                                                    <div className="flex items-center justify-between mb-1">
                                                        <span className="text-sm font-semibold text-slate-800 truncate">{s.name || s.symbol}</span>
                                                        <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${
                                                            s.action === '买入'
                                                                ? 'bg-emerald-100 text-emerald-700'
                                                                : 'bg-rose-100 text-rose-700'
                                                        }`}>{s.action}</span>
                                                    </div>
                                                    <div className="text-[11px] text-slate-500 space-y-0.5">
                                                        <div>偏离: <span className={colorForDeviation(s.deviation)}>{s.deviation > 0 ? '+' : ''}{s.deviation.toFixed(2)}%</span></div>
                                                        <div>建议金额: <b className="text-slate-700">{formatCurrency(s.suggested_amount)}</b></div>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                        <div className="mt-4 flex items-center gap-3 flex-wrap">
                                            <div className="flex items-center gap-2 text-xs">
                                                <span className="text-slate-500">阈值调整:</span>
                                                <input
                                                    type="number"
                                                    min={0.1}
                                                    max={50}
                                                    step={0.5}
                                                    value={rebalanceThreshold}
                                                    onChange={e => setRebalanceThreshold(Number(e.target.value))}
                                                    className="w-16 h-7 px-2 rounded-md border border-slate-200 text-slate-700 bg-white focus:outline-none focus:border-primary/60"
                                                />
                                                <span className="text-slate-400">%</span>
                                            </div>
                                            <div className="flex items-center gap-2 text-xs">
                                                <span className="text-slate-500">组合市值:</span>
                                                <input
                                                    type="number"
                                                    min={0}
                                                    step={10000}
                                                    value={portfolioValue}
                                                    onChange={e => setPortfolioValue(Number(e.target.value))}
                                                    className="w-28 h-7 px-2 rounded-md border border-slate-200 text-slate-700 bg-white focus:outline-none focus:border-primary/60"
                                                />
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* 关键指标卡片矩阵 */}
                        {metrics && (
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                {[
                                    { label: '年化收益', value: formatPercent(metrics.annual_return), sub: `基准 ${formatPercent(metrics.benchmark_annual_return)}`, icon: TrendingUp, good: metrics.annual_return >= 0 },
                                    { label: '超额收益', value: formatPercent(metrics.excess_return), sub: `相关性 ${metrics.correlation.toFixed(3)}`, icon: Activity, good: metrics.excess_return >= 0 },
                                    { label: '最大回撤', value: formatPercent(metrics.max_drawdown), sub: `基准 ${formatPercent(metrics.benchmark_max_drawdown)}`, icon: TrendingDown, good: metrics.max_drawdown >= metrics.benchmark_max_drawdown },
                                    { label: '夏普比率', value: metrics.sharpe_ratio.toFixed(3), sub: `IR ${metrics.information_ratio.toFixed(3)}`, icon: Target, good: metrics.sharpe_ratio >= 1 },
                                    { label: '累计收益', value: formatPercent(metrics.total_return), sub: `基准 ${formatPercent(metrics.benchmark_total_return)}`, icon: BarChart3, good: metrics.total_return >= 0 },
                                    { label: '波动率', value: formatPercent(metrics.volatility), sub: `基准 ${formatPercent(metrics.benchmark_volatility)}`, icon: AlertCircle, good: metrics.volatility <= metrics.benchmark_volatility },
                                    { label: '年化收益差', value: formatPercent(metrics.annual_return - metrics.benchmark_annual_return), sub: metrics.annual_return >= metrics.benchmark_annual_return ? '跑赢基准' : '跑输基准', icon: TrendingUp, good: metrics.annual_return >= metrics.benchmark_annual_return },
                                    { label: '回撤控制', value: formatPercent(metrics.benchmark_max_drawdown - metrics.max_drawdown), sub: metrics.max_drawdown <= metrics.benchmark_max_drawdown ? '优于基准' : '弱于基准', icon: CheckCircle, good: metrics.max_drawdown <= metrics.benchmark_max_drawdown },
                                ].map(item => {
                                    const Icon = item.icon
                                    return (
                                        <div
                                            key={item.label}
                                            className="group rounded-2xl bg-white border border-slate-200/60 p-4 shadow-sm hover:shadow-md transition-shadow"
                                        >
                                            <div className="flex items-center justify-between mb-2.5">
                                                <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">{item.label}</p>
                                                <div className={`h-7 w-7 rounded-lg flex items-center justify-center ${item.good ? 'bg-emerald-50 text-emerald-600' : 'bg-rose-50 text-rose-600'}`}>
                                                    <Icon size={14} />
                                                </div>
                                            </div>
                                            <p className={`text-2xl font-bold ${item.good ? 'text-emerald-600' : 'text-rose-600'}`}>{item.value}</p>
                                            <p className="text-[11px] text-slate-400 mt-1">{item.sub}</p>
                                        </div>
                                    )
                                })}
                            </div>
                        )}

                        {/* 权重饼图 + 历史净值曲线 */}
                        <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
                            <div className="lg:col-span-2 rounded-2xl bg-white border border-slate-200/60 p-5 shadow-sm">
                                <div className="flex items-center justify-between mb-4">
                                    <div>
                                        <h3 className="text-base font-bold text-slate-900">目标权重分布</h3>
                                        <p className="text-xs text-slate-400 mt-0.5">
                                            合计: <b className={Math.abs(totalTargetWeight - 100) < 0.5 ? 'text-emerald-600' : 'text-orange-500'}>
                                                {totalTargetWeight.toFixed(2)}%
                                            </b>
                                        </p>
                                    </div>
                                </div>
                                {(selected?.holdings?.length || 0) > 0 ? (
                                    <ReactECharts option={pieOption} style={{ height: 320 }} />
                                ) : (
                                    <div className="h-[320px] flex items-center justify-center text-sm text-slate-400">
                                        暂无持仓数据
                                    </div>
                                )}
                            </div>
                            <div className="lg:col-span-3 rounded-2xl bg-white border border-slate-200/60 p-5 shadow-sm">
                                <div className="flex items-center justify-between mb-4">
                                    <div>
                                        <h3 className="text-base font-bold text-slate-900">历史净值曲线</h3>
                                        <p className="text-xs text-slate-400 mt-0.5">
                                            {navData.length > 0
                                                ? `${navData[0].trade_date} ~ ${navData[navData.length - 1].trade_date}，共 ${navData.length} 个交易日`
                                                : '暂无净值数据'}
                                        </p>
                                    </div>
                                </div>
                                {navData.length > 0 ? (
                                    <ReactECharts option={navOption} style={{ height: 320 }} />
                                ) : (
                                    <div className="h-[320px] flex items-center justify-center text-sm text-slate-400">
                                        暂无历史净值数据（请确保持仓股票有历史价格数据）
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* 成分股表格 */}
                        <div className="rounded-2xl bg-white border border-slate-200/60 shadow-sm overflow-hidden">
                            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
                                <div>
                                    <h3 className="text-base font-bold text-slate-900">成分股明细</h3>
                                    <p className="text-xs text-slate-400 mt-0.5">
                                        {selected.holdings.length} 只成分股 · 目标权重合计 {totalTargetWeight.toFixed(2)}%
                                        {Math.abs(totalTargetWeight - 100) >= 0.5 && (
                                            <span className="text-orange-500 ml-2">（注意：权重非100%）</span>
                                        )}
                                    </p>
                                </div>
                                <button
                                    onClick={() => { setNewHolding({ symbol: '', target_weight: 20, name: '' }); setShowAddHoldingModal(true) }}
                                    className="h-9 px-4 rounded-xl bg-primary text-white text-sm font-medium hover:bg-primary/90 shadow-sm shadow-blue-200 transition-colors flex items-center gap-1.5"
                                >
                                    <Plus size={15} />添加持仓
                                </button>
                            </div>
                            <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                    <thead>
                                        <tr className="bg-slate-50/50 text-slate-500 text-xs">
                                            <th className="text-left px-5 py-3 font-medium">股票</th>
                                            <th className="text-right px-5 py-3 font-medium">最新价</th>
                                            <th className="text-right px-5 py-3 font-medium">日涨跌</th>
                                            <th className="text-right px-5 py-3 font-medium">目标权重</th>
                                            <th className="text-right px-5 py-3 font-medium">当前权重</th>
                                            <th className="text-right px-5 py-3 font-medium">偏离</th>
                                            <th className="text-center px-5 py-3 font-medium">建议</th>
                                            <th className="text-center px-5 py-3 font-medium">操作</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {(selected.holdings || []).length === 0 ? (
                                            <tr>
                                                <td colSpan={8} className="px-5 py-16 text-center text-sm text-slate-400">
                                                    暂无成分股，请点击右上角"添加持仓"
                                                </td>
                                            </tr>
                                        ) : (selected.holdings.map((h, idx) => {
                                            const dev = h.weight_deviation ?? 0
                                            const needsReb = Math.abs(dev) > rebalanceThreshold
                                            return (
                                                <tr key={h.id || idx} className={`border-t border-slate-100 ${needsReb ? 'bg-orange-50/30' : ''} hover:bg-slate-50/50 transition-colors`}>
                                                    <td className="px-5 py-3">
                                                        <div className="flex items-center gap-2.5">
                                                            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-blue-50 to-indigo-50 flex items-center justify-center text-xs font-bold text-primary">
                                                                {(h.name || h.symbol).slice(0, 1)}
                                                            </div>
                                                            <div>
                                                                <p className="font-semibold text-slate-800">{h.name || h.symbol}</p>
                                                                <p className="text-[11px] text-slate-400">{h.symbol}</p>
                                                            </div>
                                                        </div>
                                                    </td>
                                                    <td className="px-5 py-3 text-right font-medium text-slate-700 tabular-nums">
                                                        {h.latest_price ? h.latest_price.toFixed(2) : '--'}
                                                    </td>
                                                    <td className={`px-5 py-3 text-right font-medium tabular-nums ${
                                                        (h.daily_change ?? 0) > 0 ? 'text-red-500' : (h.daily_change ?? 0) < 0 ? 'text-emerald-500' : 'text-slate-400'
                                                    }`}>
                                                        {formatPercent(h.daily_change)}
                                                    </td>
                                                    <td className="px-5 py-3 text-right font-semibold text-slate-800 tabular-nums">
                                                        {h.target_weight.toFixed(2)}%
                                                    </td>
                                                    <td className="px-5 py-3 text-right font-medium text-slate-700 tabular-nums">
                                                        {(h.current_weight ?? h.target_weight).toFixed(2)}%
                                                    </td>
                                                    <td className={`px-5 py-3 text-right font-medium tabular-nums ${colorForDeviation(dev)}`}>
                                                        {dev > 0 ? '+' : ''}{dev.toFixed(2)}%
                                                    </td>
                                                    <td className="px-5 py-3 text-center">
                                                        {needsReb ? (
                                                            <span className={`inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded-md ${
                                                                dev > 0 ? 'bg-rose-100 text-rose-700' : 'bg-emerald-100 text-emerald-700'
                                                            }`}>
                                                                {dev > 0 ? '卖出' : '买入'}
                                                            </span>
                                                        ) : (
                                                            <span className="inline-flex items-center gap-1 text-[11px] text-slate-400">
                                                                <CheckCircle size={12} />正常
                                                            </span>
                                                        )}
                                                    </td>
                                                    <td className="px-5 py-3">
                                                        <div className="flex items-center justify-center gap-1.5">
                                                            <button
                                                                onClick={() => { setEditingHolding({ ...h }); setShowHoldingEditModal(true) }}
                                                                className="h-7 w-7 rounded-lg text-slate-400 hover:text-primary hover:bg-primary/5 transition-colors flex items-center justify-center"
                                                                title="编辑权重"
                                                            >
                                                                <Edit3 size={14} />
                                                            </button>
                                                            <button
                                                                onClick={() => handleDeleteHolding(h.id!)}
                                                                className="h-7 w-7 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors flex items-center justify-center"
                                                                title="移除"
                                                            >
                                                                <Trash2 size={14} />
                                                            </button>
                                                        </div>
                                                    </td>
                                                </tr>
                                            )
                                        }))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                )}
            </main>

            {/* 新建组合 Modal */}
            <Modal open={showCreateModal} onClose={() => setShowCreateModal(false)} title="新建投资组合">
                <div className="space-y-4 p-1">
                    <div>
                        <label className="text-xs font-medium text-slate-600 mb-1.5 block">组合名称 *</label>
                        <input
                            value={newPortfolio.name}
                            onChange={e => setNewPortfolio(p => ({ ...p, name: e.target.value }))}
                            placeholder="例如：核心蓝筹组合"
                            className="w-full h-10 px-3.5 rounded-xl border border-slate-200 bg-slate-50 focus:bg-white focus:border-primary/50 focus:outline-none transition-colors"
                        />
                    </div>
                    <div>
                        <label className="text-xs font-medium text-slate-600 mb-1.5 block">描述</label>
                        <textarea
                            value={newPortfolio.description}
                            onChange={e => setNewPortfolio(p => ({ ...p, description: e.target.value }))}
                            placeholder="描述该组合的投资逻辑..."
                            rows={3}
                            className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 bg-slate-50 focus:bg-white focus:border-primary/50 focus:outline-none transition-colors resize-none"
                        />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                        <div>
                            <label className="text-xs font-medium text-slate-600 mb-1.5 block">基准指数</label>
                            <Select
                                value={newPortfolio.benchmark_code}
                                onChange={v => setNewPortfolio(p => ({ ...p, benchmark_code: v }))}
                                options={BENCHMARK_OPTIONS}
                            />
                        </div>
                        <div>
                            <label className="text-xs font-medium text-slate-600 mb-1.5 block">再平衡频率</label>
                            <Select
                                value={newPortfolio.rebalance_frequency}
                                onChange={v => setNewPortfolio(p => ({ ...p, rebalance_frequency: v }))}
                                options={REBALANCE_OPTIONS}
                            />
                        </div>
                    </div>
                </div>
                <div className="flex justify-end gap-2 pt-2 mt-5 border-t border-slate-100">
                    <button
                        onClick={() => setShowCreateModal(false)}
                        className="h-9 px-4 rounded-xl border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 text-sm font-medium transition-colors"
                    >
                        取消
                    </button>
                    <button
                        onClick={handleCreate}
                        className="h-9 px-5 rounded-xl bg-primary text-white text-sm font-medium hover:bg-primary/90 shadow-sm shadow-blue-200 transition-colors flex items-center gap-1.5"
                    >
                        <Save size={15} />创建组合
                    </button>
                </div>
            </Modal>

            {/* 复制组合 Modal */}
            <Modal open={showCopyModal} onClose={() => setShowCopyModal(false)} title="复制投资组合">
                <div className="p-1 space-y-3">
                    <p className="text-sm text-slate-500">
                        将从 "<b className="text-slate-800">{selected?.name}</b>" 复制所有持仓配置
                    </p>
                    <div>
                        <label className="text-xs font-medium text-slate-600 mb-1.5 block">新组合名称 *</label>
                        <input
                            value={copyName}
                            onChange={e => setCopyName(e.target.value)}
                            placeholder={`${selected?.name || ''} 副本`}
                            className="w-full h-10 px-3.5 rounded-xl border border-slate-200 bg-slate-50 focus:bg-white focus:border-primary/50 focus:outline-none transition-colors"
                        />
                    </div>
                </div>
                <div className="flex justify-end gap-2 pt-2 mt-5 border-t border-slate-100">
                    <button
                        onClick={() => setShowCopyModal(false)}
                        className="h-9 px-4 rounded-xl border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 text-sm font-medium transition-colors"
                    >
                        取消
                    </button>
                    <button
                        onClick={handleCopy}
                        className="h-9 px-5 rounded-xl bg-primary text-white text-sm font-medium hover:bg-primary/90 shadow-sm shadow-blue-200 transition-colors flex items-center gap-1.5"
                    >
                        <Copy size={15} />确认复制
                    </button>
                </div>
            </Modal>

            {/* 添加持仓 Modal */}
            <Modal open={showAddHoldingModal} onClose={() => { setShowAddHoldingModal(false); setStockResults([]); setStockSearch('') }} title="添加持仓">
                <div className="p-1 space-y-4">
                    <div>
                        <label className="text-xs font-medium text-slate-600 mb-1.5 block">选择股票 *</label>
                        <div className="relative">
                            <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
                            <input
                                value={stockSearch}
                                onChange={e => searchStock(e.target.value)}
                                placeholder="输入代码或名称搜索..."
                                className="w-full h-10 pl-10 pr-3.5 rounded-xl border border-slate-200 bg-slate-50 focus:bg-white focus:border-primary/50 focus:outline-none transition-colors"
                            />
                        </div>
                        {stockResults.length > 0 && !newHolding.symbol && (
                            <div className="mt-2 max-h-48 overflow-y-auto rounded-xl border border-slate-100 bg-white shadow-sm">
                                {stockResults.map(s => (
                                    <button
                                        key={s.symbol}
                                        onClick={() => {
                                            setNewHolding({ symbol: s.symbol, name: s.name, target_weight: newHolding.target_weight })
                                            setStockResults([])
                                            setStockSearch(`${s.name} (${s.symbol})`)
                                        }}
                                        className="w-full flex items-center justify-between px-3.5 py-2.5 hover:bg-slate-50 text-left border-b border-slate-50 last:border-0"
                                    >
                                        <div>
                                            <span className="text-sm font-semibold text-slate-800">{s.name}</span>
                                            <span className="ml-2 text-xs text-slate-400">{s.symbol}</span>
                                        </div>
                                        <span className="text-xs text-slate-400">{s.market}</span>
                                    </button>
                                ))}
                            </div>
                        )}
                        {newHolding.symbol && (
                            <div className="mt-2 p-3 rounded-xl bg-emerald-50 border border-emerald-100 flex items-center justify-between">
                                <div>
                                    <span className="text-sm font-semibold text-emerald-800">{newHolding.name}</span>
                                    <span className="ml-2 text-xs text-emerald-600">{newHolding.symbol}</span>
                                </div>
                                <button
                                    onClick={() => { setNewHolding({ symbol: '', name: '', target_weight: newHolding.target_weight }); setStockSearch('') }}
                                    className="text-emerald-600 hover:text-emerald-700"
                                >
                                    <X size={15} />
                                </button>
                            </div>
                        )}
                    </div>
                    <div>
                        <label className="text-xs font-medium text-slate-600 mb-1.5 block">
                            目标权重 * <span className="text-slate-400">({newHolding.target_weight}%)</span>
                        </label>
                        <input
                            type="range"
                            min={0.5}
                            max={100}
                            step={0.5}
                            value={newHolding.target_weight}
                            onChange={e => setNewHolding(h => ({ ...h, target_weight: Number(e.target.value) }))}
                            className="w-full h-2 bg-slate-100 rounded-full appearance-none cursor-pointer accent-primary"
                        />
                        <div className="flex justify-between text-[10px] text-slate-400 mt-1">
                            <span>0.5%</span>
                            <span>50%</span>
                            <span>100%</span>
                        </div>
                    </div>
                    <div>
                        <label className="text-xs font-medium text-slate-600 mb-1.5 block">精确数值</label>
                        <input
                            type="number"
                            min={0.1}
                            max={100}
                            step={0.1}
                            value={newHolding.target_weight}
                            onChange={e => setNewHolding(h => ({ ...h, target_weight: Number(e.target.value) }))}
                            className="w-full h-10 px-3.5 rounded-xl border border-slate-200 bg-slate-50 focus:bg-white focus:border-primary/50 focus:outline-none transition-colors"
                        />
                    </div>
                </div>
                <div className="flex justify-end gap-2 pt-2 mt-5 border-t border-slate-100">
                    <button
                        onClick={() => { setShowAddHoldingModal(false); setStockResults([]); setStockSearch('') }}
                        className="h-9 px-4 rounded-xl border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 text-sm font-medium transition-colors"
                    >
                        取消
                    </button>
                    <button
                        onClick={handleAddHolding}
                        className="h-9 px-5 rounded-xl bg-primary text-white text-sm font-medium hover:bg-primary/90 shadow-sm shadow-blue-200 transition-colors flex items-center gap-1.5"
                    >
                        <Save size={15} />添加
                    </button>
                </div>
            </Modal>

            {/* 编辑持仓权重 Modal */}
            <Modal open={showHoldingEditModal} onClose={() => { setShowHoldingEditModal(false); setEditingHolding(null) }} title="编辑持仓权重">
                {editingHolding && (
                    <div className="p-1 space-y-4">
                        <div className="p-3 rounded-xl bg-slate-50 border border-slate-100">
                            <p className="text-sm font-semibold text-slate-800">{editingHolding.name || editingHolding.symbol}</p>
                            <p className="text-xs text-slate-400">{editingHolding.symbol}</p>
                        </div>
                        <div>
                            <label className="text-xs font-medium text-slate-600 mb-1.5 block">
                                目标权重 * <span className="text-slate-400">({editingHolding.target_weight}%)</span>
                            </label>
                            <input
                                type="range"
                                min={0.5}
                                max={100}
                                step={0.5}
                                value={editingHolding.target_weight}
                                onChange={e => setEditingHolding({ ...editingHolding, target_weight: Number(e.target.value) })}
                                className="w-full h-2 bg-slate-100 rounded-full appearance-none cursor-pointer accent-primary"
                            />
                        </div>
                        <div>
                            <label className="text-xs font-medium text-slate-600 mb-1.5 block">精确数值</label>
                            <input
                                type="number"
                                min={0.1}
                                max={100}
                                step={0.1}
                                value={editingHolding.target_weight}
                                onChange={e => setEditingHolding({ ...editingHolding, target_weight: Number(e.target.value) })}
                                className="w-full h-10 px-3.5 rounded-xl border border-slate-200 bg-slate-50 focus:bg-white focus:border-primary/50 focus:outline-none transition-colors"
                            />
                        </div>
                    </div>
                )}
                <div className="flex justify-end gap-2 pt-2 mt-5 border-t border-slate-100">
                    <button
                        onClick={() => { setShowHoldingEditModal(false); setEditingHolding(null) }}
                        className="h-9 px-4 rounded-xl border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 text-sm font-medium transition-colors"
                    >
                        取消
                    </button>
                    <button
                        onClick={handleUpdateHolding}
                        className="h-9 px-5 rounded-xl bg-primary text-white text-sm font-medium hover:bg-primary/90 shadow-sm shadow-blue-200 transition-colors flex items-center gap-1.5"
                    >
                        <Save size={15} />保存
                    </button>
                </div>
            </Modal>
        </div>
    )
}
