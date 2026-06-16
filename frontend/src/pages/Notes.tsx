import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileText, Search, Tag, Clock, TrendingUp, Filter, X, ChevronLeft, ChevronRight, FileText as FileTextIcon } from 'lucide-react'
import Loading from '../components/Loading'
import { api } from '../lib/api'
import { useToast } from '../components/Toast'
import { StockTag, StockNote } from '../types/stockNotes'
import { renderMarkdown, getNoteExcerpt } from '../utils/markdown'
import { format } from 'date-fns'
import { zhCN } from 'date-fns/locale'

export default function Notes() {
    const navigate = useNavigate()
    const { pushToast } = useToast()
    
    const [loading, setLoading] = useState(true)
    const [tags, setTags] = useState<StockTag[]>([])
    const [notes, setNotes] = useState<StockNote[]>([])
    const [total, setTotal] = useState(0)
    
    const [keyword, setKeyword] = useState('')
    const [selectedTagId, setSelectedTagId] = useState<number | null>(null)
    const [page, setPage] = useState(1)
    const [selectedNote, setSelectedNote] = useState<StockNote | null>(null)
    const [showMobileSidebar, setShowMobileSidebar] = useState(true)
    
    const pageSize = 10

    useEffect(() => {
        fetchTags()
    }, [])

    useEffect(() => {
        fetchNotes()
    }, [keyword, selectedTagId, page])

    const fetchTags = async () => {
        try {
            const res = await api.get<{ total: number; items: StockTag[] }>('/tags')
            setTags(res.data.items)
        } catch {
            pushToast('获取标签列表失败', 'error')
        }
    }

    const fetchNotes = async () => {
        setLoading(true)
        try {
            const params: any = {
                limit: pageSize,
                offset: (page - 1) * pageSize,
            }
            if (keyword) params.keyword = keyword
            if (selectedTagId) params.tag_id = selectedTagId
            
            const res = await api.get<{ total: number; items: StockNote[] }>('/notes', { params })
            setNotes(res.data.items)
            setTotal(res.data.total)
        } catch {
            pushToast('获取笔记列表失败', 'error')
        } finally {
            setLoading(false)
        }
    }

    const handleTagClick = (tagId: number | null) => {
        setSelectedTagId(tagId)
        setPage(1)
    }

    const handleNoteClick = (note: StockNote) => {
        navigate(`/stock/${note.symbol}?note=${note.id}`)
    }

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault()
        setPage(1)
    }

    const clearSearch = () => {
        setKeyword('')
        setPage(1)
    }

    const maxTagCount = useMemo(() => {
        if (tags.length === 0) return 1
        return Math.max(...tags.map(t => t.stock_count || 0), 1)
    }, [tags])

    const getTagFontSize = (count: number = 0) => {
        if (maxTagCount === 0) return 14
        const ratio = count / maxTagCount
        return 12 + ratio * 10
    }

    const totalPages = Math.ceil(total / pageSize)

    return (
        <div className="h-[calc(100vh-8rem)] flex gap-6 -mx-4">
            <div className={`${showMobileSidebar ? 'w-64' : 'w-0'} transition-all duration-300 shrink-0 overflow-hidden`}>
                <div className="w-64 h-full bg-card rounded-2xl border border-border p-5 overflow-y-auto scrollbar-thin">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="font-semibold text-sm flex items-center gap-2">
                            <Tag size={16} className="text-primary" />
                            标签云
                        </h3>
                        {selectedTagId && (
                            <button
                                onClick={() => handleTagClick(null)}
                                className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
                            >
                                <X size={12} />
                                清除
                            </button>
                        )}
                    </div>

                    <div className="flex flex-wrap gap-2">
                        {tags.length === 0 ? (
                            <p className="text-xs text-muted-foreground">暂无标签</p>
                        ) : (
                            tags.map(tag => (
                                <button
                                    key={tag.id}
                                    onClick={() => handleTagClick(selectedTagId === tag.id ? null : tag.id)}
                                    className={`px-2.5 py-1 rounded-full transition-all ${
                                        selectedTagId === tag.id
                                            ? 'ring-2 ring-offset-1 scale-105'
                                            : 'hover:scale-105'
                                    }`}
                                    style={{
                                        backgroundColor: `${tag.color}15`,
                                        color: tag.color,
                                        fontSize: `${getTagFontSize(tag.stock_count)}px`,
                                        ringColor: tag.color,
                                    }}
                                >
                                    {tag.name}
                                    <span className="ml-1 opacity-70 text-[10px]">
                                        {tag.stock_count || 0}
                                    </span>
                                </button>
                            ))
                        )}
                    </div>

                    <div className="mt-6 pt-4 border-t border-border">
                        <div className="text-xs text-muted-foreground mb-2">统计</div>
                        <div className="space-y-2">
                            <div className="flex justify-between text-sm">
                                <span className="text-muted-foreground">标签总数</span>
                                <span className="font-medium">{tags.length}</span>
                            </div>
                            <div className="flex justify-between text-sm">
                                <span className="text-muted-foreground">笔记总数</span>
                                <span className="font-medium">{total}</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <button
                onClick={() => setShowMobileSidebar(!showMobileSidebar)}
                className="absolute left-0 top-1/2 -translate-y-1/2 z-10 h-12 w-5 bg-card border border-l-0 border-border rounded-r-lg flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors hover:bg-muted"
                style={{ left: showMobileSidebar ? '256px' : '0' }}
            >
                {showMobileSidebar ? <ChevronLeft size={14} /> : <ChevronRight size={14} />}
            </button>

            <div className="flex-1 flex flex-col min-w-0">
                <div className="flex items-center justify-between gap-4 mb-4">
                    <div className="flex items-center gap-3">
                        <h1 className="text-2xl font-bold flex items-center gap-2">
                            <FileText size={24} className="text-primary" />
                            我的笔记
                        </h1>
                        <span className="text-sm text-muted-foreground">
                            共 {total} 条笔记
                        </span>
                    </div>

                    <form onSubmit={handleSearch} className="relative">
                        <div className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                            <Search size={16} />
                        </div>
                        <input
                            type="text"
                            placeholder="搜索笔记内容..."
                            value={keyword}
                            onChange={e => setKeyword(e.target.value)}
                            className="w-72 pl-9 pr-9 py-2 rounded-xl border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                        />
                        {keyword && (
                            <button
                                type="button"
                                onClick={clearSearch}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                            >
                                <X size={14} />
                            </button>
                        )}
                    </form>
                </div>

                {selectedTagId && (
                    <div className="mb-4 flex items-center gap-2">
                        <Filter size={14} className="text-muted-foreground" />
                        <span className="text-sm text-muted-foreground">当前筛选标签：</span>
                        <span
                            className="px-2 py-0.5 rounded-full text-xs font-medium text-white"
                            style={{ backgroundColor: tags.find(t => t.id === selectedTagId)?.color }}
                        >
                            {tags.find(t => t.id === selectedTagId)?.name}
                        </span>
                        <button
                            onClick={() => handleTagClick(null)}
                            className="text-xs text-primary hover:underline"
                        >
                            清除筛选
                        </button>
                    </div>
                )}

                <div className="flex-1 overflow-y-auto scrollbar-thin space-y-3 pr-2">
                    {loading ? (
                        <div className="h-64 flex items-center justify-center">
                            <Loading />
                        </div>
                    ) : notes.length === 0 ? (
                        <div className="h-64 flex flex-col items-center justify-center gap-3">
                            <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center">
                                <FileTextIcon size={24} className="text-muted-foreground" />
                            </div>
                            <p className="text-muted-foreground text-sm">
                                {keyword || selectedTagId ? '没有找到匹配的笔记' : '暂无笔记，快去个股详情页创建吧'}
                            </p>
                        </div>
                    ) : (
                        notes.map(note => (
                            <div
                                key={note.id}
                                onClick={() => handleNoteClick(note)}
                                className="bg-card rounded-xl border border-border p-5 hover:shadow-md hover:border-primary/20 transition-all cursor-pointer group"
                            >
                                <div className="flex items-start justify-between gap-4 mb-3">
                                    <div className="flex-1 min-w-0">
                                        <h3 className="font-semibold text-base group-hover:text-primary transition-colors truncate">
                                            {note.title || '无标题笔记'}
                                        </h3>
                                        <div className="flex items-center gap-3 mt-1">
                                            <span className="text-xs text-primary font-medium">
                                                {note.stock_name || note.symbol}
                                            </span>
                                            <span className="text-xs text-muted-foreground font-mono">
                                                {note.symbol}
                                            </span>
                                            <span className="text-xs text-muted-foreground flex items-center gap-1">
                                                <Clock size={12} />
                                                {format(new Date(note.updated_at), 'yyyy-MM-dd HH:mm', { locale: zhCN })}
                                            </span>
                                        </div>
                                    </div>
                                    <div className="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                                        <TrendingUp size={16} className="text-primary" />
                                    </div>
                                </div>

                                <div
                                    className="text-sm text-muted-foreground line-clamp-3"
                                    style={{ display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}
                                    dangerouslySetInnerHTML={{ __html: renderMarkdown(note.content) }}
                                />

                                {note.content.length > 150 && (
                                    <div className="mt-2 text-xs text-primary group-hover:underline">
                                        点击查看完整笔记 →
                                    </div>
                                )}
                            </div>
                        ))
                    )}

                    {!loading && notes.length > 0 && totalPages > 1 && (
                        <div className="flex items-center justify-between pt-4">
                            <div className="text-xs text-muted-foreground">
                                显示第 {(page - 1) * pageSize + 1} - {Math.min(page * pageSize, total)} 条，共 {total} 条
                            </div>
                            <div className="flex gap-2">
                                <button
                                    disabled={page <= 1}
                                    onClick={() => setPage(p => Math.max(1, p - 1))}
                                    className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium disabled:opacity-50 hover:bg-muted transition-colors"
                                >
                                    上一页
                                </button>
                                <span className="px-3 py-1.5 text-xs text-muted-foreground">
                                    {page} / {totalPages}
                                </span>
                                <button
                                    disabled={page >= totalPages}
                                    onClick={() => setPage(p => p + 1)}
                                    className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium disabled:opacity-50 hover:bg-muted transition-colors"
                                >
                                    下一页
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
