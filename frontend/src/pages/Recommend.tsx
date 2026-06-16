import { useEffect, useState, useCallback } from 'react'
import { Save, TrendingUp, BarChart2, Settings, ChevronDown, X, Star, Info } from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from '../components/Toast'
import Loading from '../components/Loading'
import Modal from '../components/Modal'
import Select from '../components/Select'

interface ScoringRule {
    rule_id: string
    name: string
    description: string
    default_weight: number
    min_value?: number
    max_value?: number
    optimal_min?: number
    optimal_max?: number
    unit: string
}

interface RuleConfig {
    rule_id: string
    weight: number
    enabled: boolean
}

interface RuleScoreDetail {
    rule_id: string
    name: string
    raw_value: number
    score: number
    weight: number
    weighted_score: number
    enabled: boolean
}

interface StockScore {
    symbol: string
    name: string
    industry?: string
    total_score: number
    max_possible_score: number
    normalized_score: number
    rule_details: RuleScoreDetail[]
}

interface ScoringCard {
    id: number
    name: string
    description?: string
    weights: Record<string, number>
    enabled_rules: Record<string, boolean>
    is_default: boolean
    created_at: string
    updated_at: string
}

const RULE_COLORS: Record<string, string> = {
    pe: 'bg-blue-500',
    pb: 'bg-cyan-500',
    rsi: 'bg-green-500',
    momentum_20d: 'bg-orange-500',
    macd_golden_cross: 'bg-red-500',
    industry_rank: 'bg-purple-500',
    market_cap: 'bg-pink-500',
}

export default function Recommend() {
    const { pushToast } = useToast()
    const [loading, setLoading] = useState(true)
    const [rules, setRules] = useState<ScoringRule[]>([])
    const [ruleConfigs, setRuleConfigs] = useState<RuleConfig[]>([])
    const [recommendations, setRecommendations] = useState<StockScore[]>([])
    const [hoveredStock, setHoveredStock] = useState<StockScore | null>(null)
    const [scoringCards, setScoringCards] = useState<ScoringCard[]>([])
    const [selectedCardId, setSelectedCardId] = useState<number | null>(null)
    const [showSaveModal, setShowSaveModal] = useState(false)
    const [saveName, setSaveName] = useState('')
    const [saveDescription, setSaveDescription] = useState('')
    const [saveAsDefault, setSaveAsDefault] = useState(false)
    const [showCardDropdown, setShowCardDropdown] = useState(false)
    const [topN, setTopN] = useState(20)

    useEffect(() => {
        loadInitialData()
    }, [])

    const loadInitialData = async () => {
        try {
            setLoading(true)
            const [rulesRes, cardsRes] = await Promise.all([
                api.get('/recommend/rules'),
                api.get('/recommend/cards'),
            ])

            const rulesData = rulesRes.data.rules
            setRules(rulesData)

            const configs: RuleConfig[] = rulesData.map((r: ScoringRule) => ({
                rule_id: r.rule_id,
                weight: r.default_weight,
                enabled: true,
            }))
            setRuleConfigs(configs)

            const cardsData = cardsRes.data.items
            setScoringCards(cardsData)

            const defaultCard = cardsData.find((c: ScoringCard) => c.is_default)
            if (defaultCard) {
                applyScoringCard(defaultCard)
            }

            await runRecommendation(configs)
        } catch (e: any) {
            console.error('加载初始数据失败:', e)
            pushToast(e.response?.data?.detail || '无法加载评分规则', 'error')
        } finally {
            setLoading(false)
        }
    }

    const runRecommendation = useCallback(async (configs: RuleConfig[]) => {
        try {
            const res = await api.post('/recommend/custom', {
                rule_configs: configs,
                n: topN,
            })
            setRecommendations(res.data.items)
        } catch (e: any) {
            console.error('获取推荐失败:', e)
            pushToast(e.response?.data?.detail || '无法获取推荐结果', 'error')
        }
    }, [topN, pushToast])

    const handleWeightChange = (ruleId: string, weight: number) => {
        const newConfigs = ruleConfigs.map((c) =>
            c.rule_id === ruleId ? { ...c, weight } : c
        )
        setRuleConfigs(newConfigs)
        runRecommendation(newConfigs)
    }

    const handleToggleEnabled = (ruleId: string) => {
        const newConfigs = ruleConfigs.map((c) =>
            c.rule_id === ruleId ? { ...c, enabled: !c.enabled } : c
        )
        setRuleConfigs(newConfigs)
        runRecommendation(newConfigs)
    }

    const handleSaveCard = async () => {
        if (!saveName.trim()) {
            pushToast('请输入方案名称', 'info')
            return
        }

        try {
            const weights: Record<string, number> = {}
            const enabled_rules: Record<string, boolean> = {}
            ruleConfigs.forEach((c) => {
                weights[c.rule_id] = c.weight
                enabled_rules[c.rule_id] = c.enabled
            })

            await api.post('/recommend/cards', {
                name: saveName,
                description: saveDescription,
                weights,
                enabled_rules,
                is_default: saveAsDefault,
            })

            pushToast(`评分卡方案 "${saveName}" 已保存`, 'success')

            setShowSaveModal(false)
            setSaveName('')
            setSaveDescription('')
            setSaveAsDefault(false)

            const res = await api.get('/recommend/cards')
            setScoringCards(res.data.items)
        } catch (e: any) {
            console.error('保存评分卡失败:', e)
            pushToast(e.response?.data?.detail || '无法保存评分卡方案', 'error')
        }
    }

    const applyScoringCard = (card: ScoringCard) => {
        const configs: RuleConfig[] = rules.map((r) => ({
            rule_id: r.rule_id,
            weight: card.weights[r.rule_id] ?? r.default_weight,
            enabled: card.enabled_rules[r.rule_id] ?? true,
        }))
        setRuleConfigs(configs)
        setSelectedCardId(card.id)
        setShowCardDropdown(false)
        runRecommendation(configs)
    }

    const handleDeleteCard = async (cardId: number, e: React.MouseEvent) => {
        e.stopPropagation()
        try {
            await api.delete(`/recommend/cards/${cardId}`)
            setScoringCards(scoringCards.filter((c) => c.id !== cardId))
            if (selectedCardId === cardId) {
                setSelectedCardId(null)
            }
            pushToast('删除成功', 'success')
        } catch (e: any) {
            console.error('删除评分卡失败:', e)
            pushToast(e.response?.data?.detail || '无法删除评分卡方案', 'error')
        }
    }

    const resetToDefault = () => {
        const configs: RuleConfig[] = rules.map((r) => ({
            rule_id: r.rule_id,
            weight: r.default_weight,
            enabled: true,
        }))
        setRuleConfigs(configs)
        setSelectedCardId(null)
        runRecommendation(configs)
    }

    const formatValue = (rule: ScoringRule, value: number): string => {
        if (rule.rule_id === 'momentum_20d') {
            return `${(value * 100).toFixed(2)}%`
        }
        if (rule.rule_id === 'industry_rank') {
            return `${(value * 100).toFixed(1)}%`
        }
        if (rule.rule_id === 'market_cap') {
            return `${value.toFixed(0)}亿`
        }
        return value.toFixed(2)
    }

    const getRuleById = (ruleId: string) => rules.find((r) => r.rule_id === ruleId)

    if (loading) {
        return <Loading />
    }

    const selectedCard = scoringCards.find((c) => c.id === selectedCardId)

    return (
        <div className="h-full flex flex-col">
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-4">
                    <div>
                        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
                            <TrendingUp className="text-primary" size={28} />
                            智能选股推荐
                        </h1>
                        <p className="text-sm text-slate-500 mt-1">
                            多维度综合打分排序，发现优质投资标的
                        </p>
                    </div>
                </div>

                <div className="flex items-center gap-3">
                    <div className="relative">
                        <button
                            onClick={() => setShowCardDropdown(!showCardDropdown)}
                            className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
                        >
                            <Settings size={18} className="text-slate-500" />
                            <span className="text-sm font-medium">
                                {selectedCard ? selectedCard.name : '默认评分卡'}
                            </span>
                            <ChevronDown size={16} className={`text-slate-400 transition-transform ${showCardDropdown ? 'rotate-180' : ''}`} />
                        </button>

                        {showCardDropdown && (
                            <div className="absolute right-0 top-full mt-2 w-72 bg-white border border-slate-200 rounded-lg shadow-lg z-50">
                                <div className="p-2 max-h-80 overflow-y-auto">
                                    <button
                                        onClick={() => {
                                            resetToDefault()
                                            setShowCardDropdown(false)
                                        }}
                                        className="w-full text-left px-3 py-2 text-sm hover:bg-slate-50 rounded-md flex items-center justify-between group"
                                    >
                                        <span className="flex items-center gap-2">
                                            <Star size={14} className="text-slate-400" />
                                            默认评分卡
                                        </span>
                                        {!selectedCardId && (
                                            <span className="text-xs text-primary font-medium">当前</span>
                                        )}
                                    </button>

                                    {scoringCards.length > 0 && (
                                        <div className="my-1 border-t border-slate-100" />
                                    )}

                                    {scoringCards.map((card) => (
                                        <div
                                            key={card.id}
                                            className="flex items-center justify-between group hover:bg-slate-50 rounded-md"
                                        >
                                            <button
                                                onClick={() => applyScoringCard(card)}
                                                className="flex-1 text-left px-3 py-2 text-sm flex items-center gap-2"
                                            >
                                                {card.is_default && <Star size={14} className="text-amber-500 fill-amber-500" />}
                                                <span className={selectedCardId === card.id ? 'text-primary font-medium' : ''}>
                                                    {card.name}
                                                </span>
                                            </button>
                                            <button
                                                onClick={(e) => handleDeleteCard(card.id, e)}
                                                className="p-1 opacity-0 group-hover:opacity-100 text-slate-400 hover:text-red-500 transition-all"
                                            >
                                                <X size={14} />
                                            </button>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>

                    <button
                        onClick={() => setShowSaveModal(true)}
                        className="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors shadow-sm shadow-blue-500/20"
                    >
                        <Save size={18} />
                        <span className="text-sm font-medium">保存当前评分卡</span>
                    </button>
                </div>
            </div>

            <div className="flex-1 flex gap-6 min-h-0">
                <div className="w-96 flex-shrink-0 bg-white border border-slate-200 rounded-2xl p-5 overflow-y-auto">
                    <div className="flex items-center justify-between mb-4">
                        <h2 className="text-lg font-semibold text-slate-800 flex items-center gap-2">
                            <Settings size={20} className="text-primary" />
                            权重配置
                        </h2>
                        <button
                            onClick={resetToDefault}
                            className="text-xs text-primary hover:text-primary/80 font-medium"
                        >
                            重置默认
                        </button>
                    </div>

                    <div className="space-y-4">
                        {ruleConfigs.map((config) => {
                            const rule = getRuleById(config.rule_id)
                            if (!rule) return null

                            return (
                                <div
                                    key={config.rule_id}
                                    className={`p-4 rounded-xl border transition-all ${
                                        config.enabled
                                            ? 'bg-white border-slate-200 hover:border-primary/30'
                                            : 'bg-slate-50 border-slate-100 opacity-60'
                                    }`}
                                >
                                    <div className="flex items-start justify-between mb-3">
                                        <div className="flex-1">
                                            <div className="flex items-center gap-2">
                                                <span className="font-medium text-slate-800 text-sm">
                                                    {rule.name}
                                                </span>
                                                <div
                                                    className={`w-2 h-2 rounded-full ${RULE_COLORS[rule.rule_id]}`}
                                                />
                                            </div>
                                            <p className="text-xs text-slate-500 mt-1">
                                                {rule.description}
                                            </p>
                                            {rule.optimal_min !== undefined && rule.optimal_max !== undefined && (
                                                <p className="text-xs text-slate-400 mt-1 flex items-center gap-1">
                                                    <Info size={12} />
                                                    最优区间: {formatValue(rule, rule.optimal_min)} ~ {formatValue(rule, rule.optimal_max)}
                                                </p>
                                            )}
                                        </div>
                                        <label className="relative inline-flex items-center cursor-pointer ml-3">
                                            <input
                                                type="checkbox"
                                                checked={config.enabled}
                                                onChange={() => handleToggleEnabled(config.rule_id)}
                                                className="sr-only peer"
                                            />
                                            <div className="w-9 h-5 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-primary"></div>
                                        </label>
                                    </div>

                                    <div className="space-y-2">
                                        <div className="flex items-center justify-between">
                                            <span className="text-xs text-slate-500">权重</span>
                                            <span className="text-xs font-medium text-primary">
                                                {config.weight.toFixed(1)}x
                                            </span>
                                        </div>
                                        <input
                                            type="range"
                                            min="0"
                                            max="3"
                                            step="0.1"
                                            value={config.weight}
                                            onChange={(e) => handleWeightChange(config.rule_id, parseFloat(e.target.value))}
                                            disabled={!config.enabled}
                                            className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-primary disabled:cursor-not-allowed"
                                        />
                                        <div className="flex justify-between text-xs text-slate-400">
                                            <span>0</span>
                                            <span className="text-slate-500">默认: {rule.default_weight}x</span>
                                            <span>3</span>
                                        </div>
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                </div>

                <div className="flex-1 flex flex-col gap-6 min-w-0">
                    <div className="flex-1 bg-white border border-slate-200 rounded-2xl p-5 overflow-hidden flex flex-col min-h-0">
                        <div className="flex items-center justify-between mb-4">
                            <h2 className="text-lg font-semibold text-slate-800 flex items-center gap-2">
                                <BarChart2 size={20} className="text-primary" />
                                推荐结果
                                <span className="text-sm font-normal text-slate-500">
                                    (Top {topN})
                                </span>
                            </h2>
                            <div className="w-28">
                                <Select
                                    value={String(topN)}
                                    onChange={(v) => {
                                        setTopN(parseInt(v))
                                        runRecommendation(ruleConfigs)
                                    }}
                                    options={[
                                        { value: '10', label: 'Top 10' },
                                        { value: '20', label: 'Top 20' },
                                        { value: '50', label: 'Top 50' },
                                    ]}
                                />
                            </div>
                        </div>

                        <div className="flex-1 overflow-auto min-h-0">
                            <table className="w-full">
                                <thead className="sticky top-0 bg-white z-10">
                                    <tr className="border-b border-slate-100">
                                        <th className="text-left py-3 px-2 text-xs font-semibold text-slate-500 uppercase tracking-wider w-16">
                                            排名
                                        </th>
                                        <th className="text-left py-3 px-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                                            股票
                                        </th>
                                        <th className="text-left py-3 px-2 text-xs font-semibold text-slate-500 uppercase tracking-wider w-32">
                                            行业
                                        </th>
                                        <th className="text-left py-3 px-2 text-xs font-semibold text-slate-500 uppercase tracking-wider w-28">
                                            总分
                                        </th>
                                        <th className="text-left py-3 px-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                                            各规则得分
                                        </th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {recommendations.map((stock, index) => (
                                        <tr
                                            key={stock.symbol}
                                            onMouseEnter={() => setHoveredStock(stock)}
                                            onMouseLeave={() => setHoveredStock(null)}
                                            className={`border-b border-slate-50 cursor-pointer transition-colors ${
                                                hoveredStock?.symbol === stock.symbol
                                                    ? 'bg-primary/5'
                                                    : 'hover:bg-slate-50'
                                            }`}
                                        >
                                            <td className="py-3 px-2">
                                                <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold ${
                                                    index < 3
                                                        ? 'bg-amber-100 text-amber-700'
                                                        : 'bg-slate-100 text-slate-500'
                                                }`}>
                                                    {index + 1}
                                                </span>
                                            </td>
                                            <td className="py-3 px-2">
                                                <div className="font-medium text-slate-900">{stock.name}</div>
                                                <div className="text-xs text-slate-500">{stock.symbol}</div>
                                            </td>
                                            <td className="py-3 px-2">
                                                <span className="inline-block px-2 py-0.5 bg-slate-100 text-slate-600 text-xs rounded-full">
                                                    {stock.industry || '-'}
                                                </span>
                                            </td>
                                            <td className="py-3 px-2">
                                                <div className="flex items-center gap-2">
                                                    <span className={`font-bold text-lg ${
                                                        stock.normalized_score >= 0.8 ? 'text-green-600' :
                                                        stock.normalized_score >= 0.6 ? 'text-blue-600' :
                                                        stock.normalized_score >= 0.4 ? 'text-amber-600' : 'text-slate-500'
                                                    }`}>
                                                        {(stock.normalized_score * 100).toFixed(0)}
                                                    </span>
                                                    <div className="w-12 h-2 bg-slate-100 rounded-full overflow-hidden">
                                                        <div
                                                            className="h-full bg-gradient-to-r from-blue-500 to-green-500 rounded-full transition-all"
                                                            style={{ width: `${stock.normalized_score * 100}%` }}
                                                        />
                                                    </div>
                                                </div>
                                            </td>
                                            <td className="py-3 px-2">
                                                <div className="flex items-center gap-1">
                                                    {stock.rule_details.filter(rd => rd.enabled).map((rd) => (
                                                        <div
                                                            key={rd.rule_id}
                                                            className="group relative"
                                                            title={`${rd.name}: ${(rd.score * 100).toFixed(0)}分`}
                                                        >
                                                            <div
                                                                className={`w-6 h-6 rounded ${RULE_COLORS[rd.rule_id]} transition-all`}
                                                                style={{ opacity: 0.3 + rd.score * 0.7 }}
                                                            />
                                                        </div>
                                                    ))}
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>

                            {recommendations.length === 0 && (
                                <div className="flex flex-col items-center justify-center py-12 text-slate-400">
                                    <TrendingUp size={48} className="mb-3 opacity-30" />
                                    <p className="text-sm">暂无推荐结果</p>
                                </div>
                            )}
                        </div>
                    </div>

                    <div className="h-64 bg-white border border-slate-200 rounded-2xl p-5 overflow-hidden flex flex-col">
                        <h2 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
                            <Info size={20} className="text-primary" />
                            评分明细
                            {hoveredStock && (
                                <span className="text-sm font-normal text-slate-500">
                                    - {hoveredStock.name} ({hoveredStock.symbol})
                                </span>
                            )}
                        </h2>

                        {hoveredStock ? (
                            <div className="flex-1 overflow-auto">
                                <div className="grid grid-cols-2 gap-3">
                                    {hoveredStock.rule_details.map((rd) => {
                                        const rule = getRuleById(rd.rule_id)
                                        if (!rule) return null

                                        return (
                                            <div
                                                key={rd.rule_id}
                                                className={`p-3 rounded-xl border ${
                                                    rd.enabled ? 'bg-white border-slate-200' : 'bg-slate-50 border-slate-100 opacity-50'
                                                }`}
                                            >
                                                <div className="flex items-center justify-between mb-2">
                                                    <div className="flex items-center gap-2">
                                                        <div
                                                            className={`w-3 h-3 rounded-full ${RULE_COLORS[rd.rule_id]}`}
                                                        />
                                                        <span className="font-medium text-slate-800 text-sm">
                                                            {rd.name}
                                                        </span>
                                                    </div>
                                                    <span className="text-xs text-slate-400">
                                                        权重 {rd.weight}x
                                                    </span>
                                                </div>

                                                <div className="flex items-center justify-between mb-1">
                                                    <span className="text-xs text-slate-500">
                                                        原始值: {rd.enabled ? formatValue(rule, rd.raw_value) : '-'}
                                                    </span>
                                                    <span className={`text-xs font-medium ${
                                                        rd.score >= 0.8 ? 'text-green-600' :
                                                        rd.score >= 0.5 ? 'text-amber-600' : 'text-red-500'
                                                    }`}>
                                                        得分 {(rd.score * 100).toFixed(0)} / 100
                                                    </span>
                                                </div>

                                                <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                                                    <div
                                                        className={`h-full rounded-full transition-all ${RULE_COLORS[rd.rule_id]}`}
                                                        style={{ width: `${rd.score * 100}%` }}
                                                    />
                                                </div>

                                                <div className="flex justify-between mt-1 text-xs text-slate-400">
                                                    <span>加权得分</span>
                                                    <span className="font-medium text-slate-600">
                                                        {(rd.weighted_score * 100 / rd.weight).toFixed(0)}分
                                                    </span>
                                                </div>
                                            </div>
                                        )
                                    })}
                                </div>
                            </div>
                        ) : (
                            <div className="flex-1 flex flex-col items-center justify-center text-slate-400">
                                <Info size={32} className="mb-2 opacity-30" />
                                <p className="text-sm">鼠标悬停在股票上查看评分明细</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            <Modal
                open={showSaveModal}
                onClose={() => setShowSaveModal(false)}
                title="保存评分卡方案"
            >
                <div className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-slate-700 mb-1">
                            方案名称 <span className="text-red-500">*</span>
                        </label>
                        <input
                            type="text"
                            value={saveName}
                            onChange={(e) => setSaveName(e.target.value)}
                            placeholder="如：价值投资评分卡"
                            className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-slate-700 mb-1">
                            方案描述
                        </label>
                        <textarea
                            value={saveDescription}
                            onChange={(e) => setSaveDescription(e.target.value)}
                            placeholder="描述该评分卡的设计思路和适用场景..."
                            rows={3}
                            className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary resize-none"
                        />
                    </div>

                    <div className="flex items-center gap-2">
                        <input
                            type="checkbox"
                            id="setDefault"
                            checked={saveAsDefault}
                            onChange={(e) => setSaveAsDefault(e.target.checked)}
                            className="w-4 h-4 text-primary rounded focus:ring-primary"
                        />
                        <label htmlFor="setDefault" className="text-sm text-slate-700">
                            设为默认评分卡方案
                        </label>
                    </div>

                    <div className="flex gap-3 pt-2">
                        <button
                            onClick={() => setShowSaveModal(false)}
                            className="flex-1 px-4 py-2 border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50 transition-colors"
                        >
                            取消
                        </button>
                        <button
                            onClick={handleSaveCard}
                            className="flex-1 px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors"
                        >
                            保存
                        </button>
                    </div>
                </div>
            </Modal>

            {showCardDropdown && (
                <div
                    className="fixed inset-0 z-40"
                    onClick={() => setShowCardDropdown(false)}
                />
            )}
        </div>
    )
}
