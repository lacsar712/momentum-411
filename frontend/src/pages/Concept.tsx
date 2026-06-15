import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import ReactECharts from 'echarts-for-react'
import { Search, ArrowUpDown, TrendingUp, TrendingDown, Layers, BarChart3 } from 'lucide-react'
import Loading from '../components/Loading'
import { api } from '../lib/api'
import Select from '../components/Select'

interface ConceptItem {
    id: number
    code: string
    name: string
    description: string | null
    category: string | null
    constituent_count: number
    daily_change: number | null
    five_day_change: number | null
}

interface LeaderboardItem {
    code: string
    name: string
    category: string | null
    constituent_count: number
    change_pct: number
}

export default function Concept() {
    const navigate = useNavigate()
    const [loading, setLoading] = useState(true)
    const [concepts, setConcepts] = useState<ConceptItem[]>([])
    const [keyword, setKeyword] = useState('')
    const [sortBy, setSortBy] = useState('five_day_change')
    const [sortOrder, setSortOrder] = useState('desc')
    const [leaderboard, setLeaderboard] = useState<LeaderboardItem[]>([])
    const [leaderboardDays, setLeaderboardDays] = useState(5)
    const [activeTab, setActiveTab] = useState<'list' | 'heat'>('list')

    const fetchConcepts = () => {
        setLoading(true)
        api.get('/concept/list', {
            params: {
                keyword,
                sort_by: sortBy,
                sort_order: sortOrder,
            }
        }).then(res => {
            setConcepts(res.data.items)
        }).finally(() => setLoading(false))
    }

    const fetchLeaderboard = () => {
        api.get('/concept/leaderboard', {
            params: {
                days: leaderboardDays,
                limit: 20,
            }
        }).then(res => {
            setLeaderboard(res.data.items)
        })
    }

    useEffect(() => {
        fetchConcepts()
        fetchLeaderboard()
    }, [keyword, sortBy, sortOrder, leaderboardDays])

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

    const leaderboardChartOption = useMemo(() => {
        const sorted = [...leaderboard].reverse()
        return {
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'shadow' },
                formatter: (params: any) => {
                    const item = params[0]
                    return `${item.name}<br/>涨跌幅: ${item.value.toFixed(2)}%`
                }
            },
            grid: { left: '3%', right: '10%', bottom: '3%', top: '3%', containLabel: true },
            xAxis: {
                type: 'value',
                axisLabel: { formatter: '{value}%' },
            },
            yAxis: {
                type: 'category',
                data: sorted.map(item => item.name),
                axisLabel: { fontSize: 12 },
            },
            series: [
                {
                    type: 'bar',
                    data: sorted.map(item => ({
                        value: item.change_pct,
                        itemStyle: {
                            color: item.change_pct >= 0 ? '#ef4444' : '#10b981',
                            borderRadius: [0, 6, 6, 0],
                        }
                    })),
                    barWidth: 16,
                    label: {
                        show: true,
                        position: 'right',
                        formatter: '{c}%',
                        fontSize: 11,
                        color: '#64748b',
                    },
                }
            ]
        }
    }, [leaderboard])

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

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-2xl font-bold tracking-tight text-slate-900">概念板块</h2>
                <p className="text-sm text-slate-500 mt-1">追踪A股热门概念板块行情与成分股</p>
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
                        <Layers size={16} />
                        板块列表
                    </div>
                </button>
                <button
                    onClick={() => setActiveTab('heat')}
                    className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                        activeTab === 'heat'
                            ? 'border-primary text-primary'
                            : 'border-transparent text-slate-500 hover:text-slate-700'
                    }`}
                >
                    <div className="flex items-center gap-2">
                        <BarChart3 size={16} />
                        热度看板
                    </div>
                </button>
            </div>

            {activeTab === 'list' && (
                <>
                    <div className="rounded-2xl border border-slate-200/60 bg-white p-4 shadow-sm">
                        <div className="flex flex-wrap gap-4 items-center justify-between">
                            <div className="relative flex-1 max-w-md">
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
                                <input
                                    type="text"
                                    placeholder="搜索概念板块名称或代码..."
                                    value={keyword}
                                    onChange={(e) => setKeyword(e.target.value)}
                                    className="w-full pl-10 pr-4 py-2.5 rounded-xl border-2 border-slate-200 text-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all"
                                />
                            </div>
                            <div className="flex gap-2 items-center">
                                <span className="text-xs text-slate-500">排序:</span>
                                <Select
                                    value={sortBy}
                                    onChange={setSortBy}
                                    options={[
                                        { value: 'name', label: '名称' },
                                        { value: 'daily_change', label: '当日涨跌幅' },
                                        { value: 'five_day_change', label: '5日涨跌幅' },
                                        { value: 'constituent_count', label: '成分股数' },
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
                                            <SortHeader field="name" label="板块名称" />
                                            <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">分类</th>
                                            <SortHeader field="daily_change" label="当日涨跌幅" />
                                            <SortHeader field="five_day_change" label="5日涨跌幅" />
                                            <SortHeader field="constituent_count" label="成分股数" />
                                            <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wider">操作</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-100">
                                        {concepts.map((item) => (
                                            <tr
                                                key={item.code}
                                                className="hover:bg-slate-50/50 cursor-pointer transition-colors"
                                                onClick={() => navigate(`/concept/${item.code}`)}
                                            >
                                                <td className="px-4 py-4">
                                                    <div className="flex items-center gap-3">
                                                        <div className="h-10 w-10 rounded-xl bg-primary/10 flex items-center justify-center">
                                                            <Layers size={18} className="text-primary" />
                                                        </div>
                                                        <div>
                                                            <p className="text-sm font-semibold text-slate-900">{item.name}</p>
                                                            <p className="text-xs text-slate-400">{item.code}</p>
                                                        </div>
                                                    </div>
                                                </td>
                                                <td className="px-4 py-4">
                                                    {item.category && (
                                                        <span className="inline-flex items-center px-2 py-1 rounded-lg bg-slate-100 text-xs font-medium text-slate-600">
                                                            {item.category}
                                                        </span>
                                                    )}
                                                </td>
                                                <td className="px-4 py-4">
                                                    <span className={`text-sm font-semibold ${getChangeColor(item.daily_change)}`}>
                                                        {formatChange(item.daily_change)}
                                                    </span>
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
                                                <td className="px-4 py-4">
                                                    <span className="text-sm text-slate-600">{item.constituent_count} 只</span>
                                                </td>
                                                <td className="px-4 py-4 text-right">
                                                    <button
                                                        onClick={(e) => {
                                                            e.stopPropagation()
                                                            navigate(`/concept/${item.code}`)
                                                        }}
                                                        className="text-xs font-medium text-primary hover:text-primary/80"
                                                    >
                                                        查看详情 →
                                                    </button>
                                                </td>
                                            </tr>
                                        ))}
                                        {concepts.length === 0 && (
                                            <tr>
                                                <td colSpan={6} className="px-4 py-12 text-center text-slate-400">
                                                    暂无概念板块数据
                                                </td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </div>
                </>
            )}

            {activeTab === 'heat' && (
                <div className="rounded-2xl border border-slate-200/60 bg-white p-6 shadow-sm">
                    <div className="flex items-center justify-between mb-6">
                        <div>
                            <h3 className="text-lg font-bold text-slate-900">概念热度排行榜</h3>
                            <p className="text-xs text-slate-400 mt-1">按周期涨跌幅排序</p>
                        </div>
                        <div className="flex gap-2">
                            {[5, 10, 20].map(days => (
                                <button
                                    key={days}
                                    onClick={() => setLeaderboardDays(days)}
                                    className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                                        leaderboardDays === days
                                            ? 'bg-primary text-white shadow-sm'
                                            : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                                    }`}
                                >
                                    {days}日
                                </button>
                            ))}
                        </div>
                    </div>
                    {leaderboard.length > 0 ? (
                        <ReactECharts option={leaderboardChartOption} style={{ height: 500 }} />
                    ) : (
                        <div className="h-[500px] flex items-center justify-center text-slate-400">
                            暂无数据
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}
