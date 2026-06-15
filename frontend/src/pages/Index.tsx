import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, ArrowUpDown, TrendingUp, TrendingDown, CandlestickChart, Timer, GitCompare, Filter } from 'lucide-react'
import Loading from '../components/Loading'
import { api } from '../lib/api'
import Select from '../components/Select'
import DatePicker from '../components/DatePicker'

interface IndexItem {
    id: number
    code: string
    name: string
    index_type: 'index' | 'etf'
    tracking_target: string | null
    list_date: string | null
    daily_change: number | null
    five_day_change: number | null
    latest_close: number | null
    latest_volume: number | null
    latest_amount: number | null
}

export default function Index() {
    const navigate = useNavigate()
    const [loading, setLoading] = useState(true)
    const [indices, setIndices] = useState<IndexItem[]>([])
    const [keyword, setKeyword] = useState('')
    const [indexType, setIndexType] = useState<string>('all')
    const [sortBy, setSortBy] = useState('five_day_change')
    const [sortOrder, setSortOrder] = useState('desc')
    const [activeTab, setActiveTab] = useState<'list' | 'quick'>('list')
    const [backtestStart, setBacktestStart] = useState('')
    const [backtestEnd, setBacktestEnd] = useState('')

    const fetchIndices = () => {
        setLoading(true)
        const params: Record<string, any> = {
            keyword,
            sort_by: sortBy,
            sort_order: sortOrder,
        }
        if (indexType !== 'all') {
            params.index_type = indexType
        }
        api.get('/index/list', { params })
            .then(res => {
                setIndices(res.data.items)
            })
            .finally(() => setLoading(false))
    }

    useEffect(() => {
        fetchIndices()
    }, [keyword, indexType, sortBy, sortOrder])

    useEffect(() => {
        const today = new Date()
        const oneYearAgo = new Date()
        oneYearAgo.setFullYear(today.getFullYear() - 1)
        setBacktestEnd(today.toISOString().split('T')[0])
        setBacktestStart(oneYearAgo.toISOString().split('T')[0])
    }, [])

    const handleSort = (field: string) => {
        if (sortBy === field) {
            setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
        } else {
            setSortBy(field)
            setSortOrder('desc')
        }
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

    const formatVolume = (val: number | null) => {
        if (val === null || val === undefined) return '--'
        if (val >= 1e8) return `${(val / 1e8).toFixed(2)}亿`
        if (val >= 1e4) return `${(val / 1e4).toFixed(2)}万`
        return val.toFixed(0)
    }

    const handleBacktestAsBenchmark = (item: IndexItem) => {
        const params = new URLSearchParams({
            strategy: 'dual_ma',
            symbols: item.tracking_target || item.code,
            start: backtestStart,
            end: backtestEnd,
            benchmark: item.code,
        })
        navigate(`/backtest?${params.toString()}`)
    }

    const handleCompare = (codes: string[]) => {
        const params = new URLSearchParams({ codes: codes.join(',') })
        navigate(`/index-compare?${params.toString()}`)
    }

    const SortHeader = ({ field, label }: { field: string; label: string }) => (
        <th
            className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider cursor-pointer hover:text-slate-700 select-none"
            onClick={() => handleSort(field)}
        >
            <div className="flex items-center gap-1.5">
                {label}
                <ArrowUpDown size={14} className={sortBy === field ? 'text-primary' : 'text-slate-300'} />
            </div>
        </th>
    )

    const statsCards = useMemo(() => {
        const indexCount = indices.filter(i => i.index_type === 'index').length
        const etfCount = indices.filter(i => i.index_type === 'etf').length
        const upCount = indices.filter(i => i.daily_change !== null && i.daily_change > 0).length
        const downCount = indices.filter(i => i.daily_change !== null && i.daily_change < 0).length
        return [
            { label: '指数数量', value: indexCount, color: 'text-blue-600', bg: 'bg-blue-50' },
            { label: 'ETF数量', value: etfCount, color: 'text-purple-600', bg: 'bg-purple-50' },
            { label: '上涨', value: upCount, color: 'text-red-500', bg: 'bg-red-50' },
            { label: '下跌', value: downCount, color: 'text-emerald-500', bg: 'bg-emerald-50' },
        ]
    }, [indices])

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold tracking-tight text-slate-900">指数与ETF监控</h2>
                    <p className="text-sm text-slate-500 mt-1">追踪A股主要指数与ETF行情，支持多维度分析对比</p>
                </div>
                <button
                    onClick={() => navigate('/index-compare')}
                    className="flex items-center gap-2 h-10 px-4 rounded-xl bg-primary text-white text-sm font-medium shadow-sm hover:bg-primary/90 transition-colors"
                >
                    <GitCompare size={16} />
                    指数对比
                </button>
            </div>

            <div className="grid grid-cols-4 gap-4">
                {statsCards.map((stat, idx) => (
                    <div key={idx} className="rounded-2xl border border-slate-200/60 bg-white p-4 shadow-sm">
                        <div className="flex items-center justify-between">
                            <p className="text-xs font-medium text-slate-500">{stat.label}</p>
                            <div className={`h-8 w-8 rounded-lg ${stat.bg} flex items-center justify-center`}>
                                <CandlestickChart size={14} className={stat.color} />
                            </div>
                        </div>
                        <p className={`text-2xl font-bold mt-2 ${stat.color}`}>{stat.value}</p>
                    </div>
                ))}
            </div>

            <div className="flex gap-2 border-b border-slate-200">
                <button
                    onClick={() => setActiveTab('list')}
                    className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                        activeTab === 'list'
                            ? 'border-primary text-primary'
                            : 'border-transparent text-slate-500 hover:text-slate-700'
                    }`}
                >
                    <div className="flex items-center gap-2">
                        <CandlestickChart size={16} />
                        列表视图
                    </div>
                </button>
                <button
                    onClick={() => setActiveTab('quick')}
                    className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                        activeTab === 'quick'
                            ? 'border-primary text-primary'
                            : 'border-transparent text-slate-500 hover:text-slate-700'
                    }`}
                >
                    <div className="flex items-center gap-2">
                        <Timer size={16} />
                        回测基准设置
                    </div>
                </button>
            </div>

            {activeTab === 'quick' && (
                <div className="rounded-2xl border border-slate-200/60 bg-white p-5 shadow-sm">
                    <h3 className="text-sm font-semibold text-slate-900 mb-4">默认回测时间区间</h3>
                    <div className="grid grid-cols-2 gap-4 max-w-xl">
                        <div>
                            <label className="text-xs font-medium text-slate-500 mb-1 block">开始日期</label>
                            <DatePicker value={backtestStart} onChange={setBacktestStart} />
                        </div>
                        <div>
                            <label className="text-xs font-medium text-slate-500 mb-1 block">结束日期</label>
                            <DatePicker value={backtestEnd} onChange={setBacktestEnd} />
                        </div>
                    </div>
                    <p className="text-xs text-slate-400 mt-3">设置后，点击"作为回测基准"按钮将自动带此参数跳转至回测页面</p>
                </div>
            )}

            <div className="rounded-2xl border border-slate-200/60 bg-white p-4 shadow-sm">
                <div className="flex flex-wrap gap-4 items-center justify-between">
                    <div className="flex flex-wrap items-center gap-3 flex-1">
                        <div className="relative max-w-md flex-1 min-w-[240px]">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
                            <input
                                type="text"
                                placeholder="搜索指数/ETF名称或代码..."
                                value={keyword}
                                onChange={(e) => setKeyword(e.target.value)}
                                className="w-full pl-10 pr-4 py-2.5 rounded-xl border-2 border-slate-200 text-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all"
                            />
                        </div>
                        <div className="flex items-center gap-2">
                            <Filter size={16} className="text-slate-400" />
                            <Select
                                value={indexType}
                                onChange={setIndexType}
                                options={[
                                    { value: 'all', label: '全部类型' },
                                    { value: 'index', label: '仅指数' },
                                    { value: 'etf', label: '仅ETF' },
                                ]}
                            />
                        </div>
                    </div>
                    <div className="flex gap-2 items-center">
                        <span className="text-xs text-slate-500">排序:</span>
                        <Select
                            value={sortBy}
                            onChange={setSortBy}
                            options={[
                                { value: 'name', label: '名称' },
                                { value: 'code', label: '代码' },
                                { value: 'daily_change', label: '当日涨跌幅' },
                                { value: 'five_day_change', label: '5日涨跌幅' },
                                { value: 'latest_amount', label: '成交额' },
                            ]}
                        />
                        <button
                            onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
                            className="h-10 px-3 rounded-xl border-2 border-slate-200 text-sm font-medium hover:border-primary/50 transition-colors"
                        >
                            {sortOrder === 'asc' ? '升序' : '降序'}
                        </button>
                    </div>
                </div>
            </div>

            <div className="rounded-2xl border border-slate-200/60 bg-white shadow-sm overflow-hidden">
                {loading ? (
                    <div className="p-12"><Loading /></div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead className="bg-slate-50/80">
                                <tr>
                                    <SortHeader field="name" label="名称" />
                                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">类型</th>
                                    <SortHeader field="daily_change" label="当日涨跌" />
                                    <SortHeader field="five_day_change" label="5日涨跌" />
                                    <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wider">最新价</th>
                                    <SortHeader field="latest_amount" label="成交额" />
                                    <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wider">操作</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                                {indices.map((item) => (
                                    <tr
                                        key={item.code}
                                        className="hover:bg-slate-50/50 cursor-pointer transition-colors"
                                        onClick={() => navigate(`/index/${item.code}`)}
                                    >
                                        <td className="px-4 py-4">
                                            <div className="flex items-center gap-3">
                                                <div className={`h-10 w-10 rounded-xl flex items-center justify-center ${
                                                    item.index_type === 'index' ? 'bg-blue-50' : 'bg-purple-50'
                                                }`}>
                                                    <CandlestickChart size={18} className={
                                                        item.index_type === 'index' ? 'text-blue-600' : 'text-purple-600'
                                                    } />
                                                </div>
                                                <div>
                                                    <p className="text-sm font-semibold text-slate-900">{item.name}</p>
                                                    <p className="text-xs text-slate-400">
                                                        {item.code}
                                                        {item.tracking_target && ` · 跟踪 ${item.tracking_target}`}
                                                    </p>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="px-4 py-4">
                                            <span className={`inline-flex items-center px-2 py-1 rounded-lg text-xs font-medium ${
                                                item.index_type === 'index'
                                                    ? 'bg-blue-50 text-blue-600'
                                                    : 'bg-purple-50 text-purple-600'
                                            }`}>
                                                {item.index_type === 'index' ? '指数' : 'ETF'}
                                            </span>
                                        </td>
                                        <td className="px-4 py-4">
                                            <div className="flex items-center gap-1.5">
                                                {item.daily_change !== null && item.daily_change !== undefined && (
                                                    item.daily_change >= 0
                                                        ? <TrendingUp size={14} className="text-red-500" />
                                                        : <TrendingDown size={14} className="text-emerald-500" />
                                                )}
                                                <span className={`text-sm font-semibold ${getChangeColor(item.daily_change)}`}>
                                                    {formatChange(item.daily_change)}
                                                </span>
                                            </div>
                                        </td>
                                        <td className="px-4 py-4">
                                            <div className="flex items-center gap-1.5">
                                                {item.five_day_change !== null && item.five_day_change !== undefined && (
                                                    item.five_day_change >= 0
                                                        ? <TrendingUp size={14} className="text-red-500" />
                                                        : <TrendingDown size={14} className="text-emerald-500" />
                                                )}
                                                <span className={`text-sm font-semibold ${getChangeColor(item.five_day_change)}`}>
                                                    {formatChange(item.five_day_change)}
                                                </span>
                                            </div>
                                        </td>
                                        <td className="px-4 py-4 text-right">
                                            <span className="text-sm font-semibold text-slate-900">
                                                {item.latest_close !== null ? item.latest_close.toFixed(2) : '--'}
                                            </span>
                                        </td>
                                        <td className="px-4 py-4 text-right">
                                            <span className="text-sm text-slate-600">
                                                {formatVolume(item.latest_amount)}
                                            </span>
                                        </td>
                                        <td className="px-4 py-4">
                                            <div className="flex items-center justify-end gap-1" onClick={e => e.stopPropagation()}>
                                                <button
                                                    onClick={() => handleBacktestAsBenchmark(item)}
                                                    className="px-2.5 py-1.5 rounded-lg text-xs font-medium bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
                                                    title="作为回测基准跳转至回测页面"
                                                >
                                                    回测基准
                                                </button>
                                                <button
                                                    onClick={() => navigate(`/index/${item.code}`)}
                                                    className="px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-600 hover:bg-slate-100 transition-colors"
                                                >
                                                    详情 →
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                                {indices.length === 0 && (
                                    <tr>
                                        <td colSpan={7} className="px-4 py-12 text-center text-slate-400">
                                            暂无指数/ETF数据
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            {activeTab === 'list' && indices.length >= 2 && (
                <div className="rounded-2xl border border-slate-200/60 bg-white p-4 shadow-sm">
                    <div className="flex items-center justify-between">
                        <div>
                            <h3 className="text-sm font-semibold text-slate-900">快速对比</h3>
                            <p className="text-xs text-slate-400 mt-1">勾选多个指数/ETF进行归一化走势对比（支持2~4个）</p>
                        </div>
                        <button
                            onClick={() => {
                                const selected = indices.slice(0, 4).map(i => i.code)
                                handleCompare(selected)
                            }}
                            className="flex items-center gap-2 h-9 px-3 rounded-lg border-2 border-slate-200 text-sm font-medium text-slate-600 hover:border-primary hover:text-primary transition-colors"
                        >
                            <GitCompare size={14} />
                            一键对比前4个
                        </button>
                    </div>
                </div>
            )}
        </div>
    )
}
