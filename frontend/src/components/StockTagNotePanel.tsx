import { useState, useEffect, useRef } from 'react'
import { X, Plus, Search, Edit3, Trash2, Clock, Tag, FileText, Save, ChevronDown, ChevronUp } from 'lucide-react'
import { api } from '../lib/api'
import { useToast } from './Toast'
import { StockTag, StockNote, StockTagNoteAggregate } from '../types/stockNotes'
import { renderMarkdown } from '../utils/markdown'
import { format } from 'date-fns'
import { zhCN } from 'date-fns/locale'

interface StockTagNotePanelProps {
    symbol: string
    stockName?: string
}

const DEFAULT_COLORS = [
    '#3b82f6', '#ef4444', '#22c55e', '#f59e0b', '#8b5cf6',
    '#ec4899', '#06b6d4', '#f97316', '#64748b', '#84cc16'
]

export default function StockTagNotePanel({ symbol, stockName }: StockTagNotePanelProps) {
    const { pushToast } = useToast()
    const [loading, setLoading] = useState(true)
    const [tags, setTags] = useState<StockTag[]>([])
    const [notes, setNotes] = useState<StockNote[]>([])
    const [allTags, setAllTags] = useState<StockTag[]>([])
    
    const [showTagSelector, setShowTagSelector] = useState(false)
    const [tagSearch, setTagSearch] = useState('')
    const [showCreateTag, setShowCreateTag] = useState(false)
    const [newTagName, setNewTagName] = useState('')
    const [newTagColor, setNewTagColor] = useState('#3b82f6')
    const [newTagDesc, setNewTagDesc] = useState('')
    
    const [editingNote, setEditingNote] = useState<StockNote | null>(null)
    const [isCreatingNote, setIsCreatingNote] = useState(false)
    const [noteTitle, setNoteTitle] = useState('')
    const [noteContent, setNoteContent] = useState('')
    const [autoSaveTimer, setAutoSaveTimer] = useState<number | null>(null)
    const [draftKey, setDraftKey] = useState('')
    
    const [expandedNotes, setExpandedNotes] = useState<Set<number>>(new Set())
    const [showTimeline, setShowTimeline] = useState(true)
    
    const draftSavedRef = useRef(false)

    useEffect(() => {
        const key = `note_draft_${symbol}`
        setDraftKey(key)
        fetchData()
        fetchAllTags()
    }, [symbol])

    useEffect(() => {
        if (isCreatingNote || editingNote) {
            const saved = localStorage.getItem(draftKey)
            if (saved) {
                try {
                    const data = JSON.parse(saved)
                    if (data.title !== undefined) setNoteTitle(data.title)
                    if (data.content !== undefined) setNoteContent(data.content)
                } catch {}
            }
        }
    }, [isCreatingNote, editingNote, draftKey])

    const fetchData = async () => {
        setLoading(true)
        try {
            const res = await api.get<StockTagNoteAggregate>(`/stock/${symbol}/tags_notes`)
            setTags(res.data.tags)
            setNotes(res.data.notes)
        } catch (e) {
            pushToast('获取标签与笔记失败', 'error')
        } finally {
            setLoading(false)
        }
    }

    const fetchAllTags = async () => {
        try {
            const res = await api.get<{ total: number; items: StockTag[] }>('/tags')
            setAllTags(res.data.items)
        } catch {}
    }

    const handleRemoveTag = async (tagId: number) => {
        const newTagIds = tags.filter(t => t.id !== tagId).map(t => t.id)
        try {
            await api.post('/tags/assign', { symbol, tag_ids: newTagIds })
            setTags(tags.filter(t => t.id !== tagId))
            pushToast('已移除标签', 'success')
        } catch {
            pushToast('移除标签失败', 'error')
        }
    }

    const handleAddTag = async (tag: StockTag) => {
        if (tags.find(t => t.id === tag.id)) return
        const newTagIds = [...tags.map(t => t.id), tag.id]
        try {
            await api.post('/tags/assign', { symbol, tag_ids: newTagIds })
            setTags([...tags, tag])
            setShowTagSelector(false)
            pushToast('已添加标签', 'success')
        } catch {
            pushToast('添加标签失败', 'error')
        }
    }

    const handleCreateTag = async () => {
        if (!newTagName.trim()) {
            pushToast('请输入标签名称', 'error')
            return
        }
        try {
            const res = await api.post<StockTag>('/tags', {
                name: newTagName.trim(),
                color: newTagColor,
                description: newTagDesc || undefined,
            })
            const newTag = res.data
            setAllTags([newTag, ...allTags])
            
            const newTagIds = [...tags.map(t => t.id), newTag.id]
            await api.post('/tags/assign', { symbol, tag_ids: newTagIds })
            setTags([...tags, newTag])
            
            setNewTagName('')
            setNewTagDesc('')
            setShowCreateTag(false)
            setShowTagSelector(false)
            pushToast('标签创建成功', 'success')
        } catch (e: any) {
            pushToast(e.response?.data?.detail || '创建标签失败', 'error')
        }
    }

    const handleStartCreateNote = () => {
        setNoteTitle('')
        setNoteContent('')
        setIsCreatingNote(true)
        setEditingNote(null)
        localStorage.removeItem(draftKey)
        draftSavedRef.current = false
    }

    const handleStartEditNote = (note: StockNote) => {
        setEditingNote(note)
        setNoteTitle(note.title || '')
        setNoteContent(note.content)
        setIsCreatingNote(false)
        localStorage.removeItem(draftKey)
        draftSavedRef.current = false
    }

    const handleAutoSave = (title: string, content: string) => {
        if (autoSaveTimer) clearTimeout(autoSaveTimer)
        const timer = window.setTimeout(() => {
            localStorage.setItem(draftKey, JSON.stringify({ title, content, savedAt: Date.now() }))
            draftSavedRef.current = true
        }, 1000)
        setAutoSaveTimer(timer)
    }

    const handleNoteTitleChange = (val: string) => {
        setNoteTitle(val)
        handleAutoSave(val, noteContent)
    }

    const handleNoteContentChange = (val: string) => {
        setNoteContent(val)
        handleAutoSave(noteTitle, val)
    }

    const handleSaveNote = async () => {
        try {
            if (editingNote) {
                const res = await api.put<StockNote>(`/notes/${editingNote.id}`, {
                    title: noteTitle || undefined,
                    content: noteContent,
                })
                setNotes(notes.map(n => n.id === editingNote.id ? res.data : n))
                pushToast('笔记已更新', 'success')
            } else {
                const res = await api.post<StockNote>('/notes', {
                    symbol,
                    title: noteTitle || undefined,
                    content: noteContent,
                })
                setNotes([res.data, ...notes])
                pushToast('笔记已保存', 'success')
            }
            setEditingNote(null)
            setIsCreatingNote(false)
            localStorage.removeItem(draftKey)
            draftSavedRef.current = false
        } catch {
            pushToast('保存笔记失败', 'error')
        }
    }

    const handleDeleteNote = async (noteId: number) => {
        if (!confirm('确定要删除这条笔记吗？')) return
        try {
            await api.delete(`/notes/${noteId}`)
            setNotes(notes.filter(n => n.id !== noteId))
            if (editingNote?.id === noteId) {
                setEditingNote(null)
            }
            pushToast('笔记已删除', 'success')
        } catch {
            pushToast('删除笔记失败', 'error')
        }
    }

    const handleCancelEdit = () => {
        if (noteContent || noteTitle) {
            if (!confirm('确定要放弃编辑吗？草稿将被清除。')) return
        }
        setEditingNote(null)
        setIsCreatingNote(false)
        localStorage.removeItem(draftKey)
        draftSavedRef.current = false
    }

    const toggleNoteExpand = (noteId: number) => {
        const newSet = new Set(expandedNotes)
        if (newSet.has(noteId)) {
            newSet.delete(noteId)
        } else {
            newSet.add(noteId)
        }
        setExpandedNotes(newSet)
    }

    const filteredAllTags = allTags.filter(t =>
        !tags.find(st => st.id === t.id) &&
        (tagSearch === '' || t.name.toLowerCase().includes(tagSearch.toLowerCase()))
    )

    const hasDraft = isCreatingNote || editingNote

    return (
        <div className="w-80 bg-card border-l border-border flex flex-col h-full overflow-hidden">
            <div className="p-4 border-b border-border bg-muted/30">
                <h3 className="font-semibold text-sm flex items-center gap-2">
                    <Tag size={16} className="text-primary" />
                    我的标签与笔记
                </h3>
            </div>

            <div className="flex-1 overflow-y-auto scrollbar-thin">
                <div className="p-4 border-b border-border">
                    <div className="flex items-center justify-between mb-3">
                        <span className="text-xs font-medium text-muted-foreground">标签</span>
                        <button
                            onClick={() => setShowTagSelector(!showTagSelector)}
                            className="h-6 w-6 rounded-md bg-primary/10 text-primary hover:bg-primary/20 transition-colors flex items-center justify-center"
                        >
                            <Plus size={14} />
                        </button>
                    </div>

                    {showTagSelector && (
                        <div className="mb-3 p-3 bg-muted/50 rounded-lg border border-border">
                            <div className="relative mb-2">
                                <Search size={14} className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
                                <input
                                    type="text"
                                    placeholder="搜索标签..."
                                    value={tagSearch}
                                    onChange={e => setTagSearch(e.target.value)}
                                    className="w-full pl-8 pr-3 py-1.5 text-xs rounded-md border border-input bg-background focus:outline-none focus:ring-2 focus:ring-primary/20"
                                />
                            </div>
                            
                            {!showCreateTag ? (
                                <button
                                    onClick={() => setShowCreateTag(true)}
                                    className="w-full text-xs text-primary hover:bg-primary/5 py-1.5 rounded-md transition-colors flex items-center justify-center gap-1 mb-2"
                                >
                                    <Plus size={12} />
                                    创建新标签
                                </button>
                            ) : (
                                <div className="space-y-2 mb-2">
                                    <input
                                        type="text"
                                        placeholder="标签名称"
                                        value={newTagName}
                                        onChange={e => setNewTagName(e.target.value)}
                                        className="w-full px-2 py-1.5 text-xs rounded-md border border-input bg-background focus:outline-none focus:ring-2 focus:ring-primary/20"
                                    />
                                    <div className="flex gap-1 flex-wrap">
                                        {DEFAULT_COLORS.map(color => (
                                            <button
                                                key={color}
                                                onClick={() => setNewTagColor(color)}
                                                className={`h-5 w-5 rounded-full transition-transform ${newTagColor === color ? 'ring-2 ring-offset-1 ring-primary scale-110' : ''}`}
                                                style={{ backgroundColor: color }}
                                            />
                                        ))}
                                    </div>
                                    <input
                                        type="text"
                                        placeholder="描述（可选）"
                                        value={newTagDesc}
                                        onChange={e => setNewTagDesc(e.target.value)}
                                        className="w-full px-2 py-1.5 text-xs rounded-md border border-input bg-background focus:outline-none focus:ring-2 focus:ring-primary/20"
                                    />
                                    <div className="flex gap-2">
                                        <button
                                            onClick={handleCreateTag}
                                            className="flex-1 text-xs bg-primary text-white py-1.5 rounded-md hover:bg-primary/90 transition-colors"
                                        >
                                            创建并添加
                                        </button>
                                        <button
                                            onClick={() => { setShowCreateTag(false); setNewTagName(''); setNewTagDesc('') }}
                                            className="text-xs text-muted-foreground hover:text-foreground py-1.5 px-3 transition-colors"
                                        >
                                            取消
                                        </button>
                                    </div>
                                </div>
                            )}

                            <div className="max-h-32 overflow-y-auto space-y-1">
                                {filteredAllTags.length === 0 ? (
                                    <p className="text-xs text-muted-foreground text-center py-2">暂无可用标签</p>
                                ) : (
                                    filteredAllTags.map(tag => (
                                        <button
                                            key={tag.id}
                                            onClick={() => handleAddTag(tag)}
                                            className="w-full flex items-center gap-2 px-2 py-1.5 text-xs hover:bg-background rounded-md transition-colors text-left"
                                        >
                                            <span className="h-3 w-3 rounded-full" style={{ backgroundColor: tag.color }} />
                                            <span className="flex-1 truncate">{tag.name}</span>
                                            <Plus size={12} className="text-muted-foreground" />
                                        </button>
                                    ))
                                )}
                            </div>
                        </div>
                    )}

                    <div className="flex flex-wrap gap-1.5">
                        {tags.length === 0 ? (
                            <p className="text-xs text-muted-foreground">暂无标签，点击 + 添加</p>
                        ) : (
                            tags.map(tag => (
                                <span
                                    key={tag.id}
                                    className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium text-white"
                                    style={{ backgroundColor: tag.color }}
                                >
                                    {tag.name}
                                    <button
                                        onClick={() => handleRemoveTag(tag.id)}
                                        className="hover:bg-black/20 rounded-full p-0.5 transition-colors"
                                    >
                                        <X size={10} />
                                    </button>
                                </span>
                            ))
                        )}
                    </div>
                </div>

                <div className="p-4">
                    <div className="flex items-center justify-between mb-3">
                        <button
                            onClick={() => setShowTimeline(!showTimeline)}
                            className="text-xs font-medium text-muted-foreground flex items-center gap-1 hover:text-foreground transition-colors"
                        >
                            <FileText size={14} />
                            历史笔记
                            {showTimeline ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                            <span className="text-muted-foreground/70">({notes.length})</span>
                        </button>
                        <button
                            onClick={handleStartCreateNote}
                            className="text-xs text-primary hover:bg-primary/10 px-2 py-1 rounded-md transition-colors flex items-center gap-1"
                        >
                            <Edit3 size={12} />
                            新建
                        </button>
                    </div>

                    {hasDraft && (
                        <div className="mb-4 p-3 bg-blue-50 border border-blue-100 rounded-lg">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-xs font-medium text-blue-700">
                                    {editingNote ? '编辑笔记' : '新建笔记'}
                                </span>
                                <span className="text-[10px] text-blue-500">草稿自动保存</span>
                            </div>
                            <input
                                type="text"
                                placeholder="标题（可选）"
                                value={noteTitle}
                                onChange={e => handleNoteTitleChange(e.target.value)}
                                className="w-full px-2 py-1.5 text-xs rounded-md border border-blue-200 bg-white mb-2 focus:outline-none focus:ring-2 focus:ring-blue-200"
                            />
                            <div className="grid grid-cols-2 gap-2">
                                <div>
                                    <label className="text-[10px] text-blue-600 mb-1 block">编辑</label>
                                    <textarea
                                        value={noteContent}
                                        onChange={e => handleNoteContentChange(e.target.value)}
                                        placeholder="支持 Markdown..."
                                        className="w-full h-32 px-2 py-1.5 text-xs rounded-md border border-blue-200 bg-white resize-none focus:outline-none focus:ring-2 focus:ring-blue-200 font-mono"
                                    />
                                </div>
                                <div>
                                    <label className="text-[10px] text-blue-600 mb-1 block">预览</label>
                                    <div
                                        className="w-full h-32 px-2 py-1.5 text-xs rounded-md border border-blue-200 bg-white overflow-y-auto prose prose-xs"
                                        dangerouslySetInnerHTML={{ __html: renderMarkdown(noteContent) }}
                                    />
                                </div>
                            </div>
                            <div className="flex gap-2 mt-2">
                                <button
                                    onClick={handleSaveNote}
                                    className="flex-1 text-xs bg-blue-600 text-white py-1.5 rounded-md hover:bg-blue-700 transition-colors flex items-center justify-center gap-1"
                                >
                                    <Save size={12} />
                                    保存
                                </button>
                                <button
                                    onClick={handleCancelEdit}
                                    className="text-xs text-muted-foreground hover:text-foreground py-1.5 px-3 transition-colors"
                                >
                                    取消
                                </button>
                            </div>
                        </div>
                    )}

                    {showTimeline && (
                        <div className="space-y-3">
                            {notes.length === 0 ? (
                                <p className="text-xs text-muted-foreground text-center py-4">暂无笔记</p>
                            ) : (
                                notes.map((note, index) => (
                                    <div
                                        key={note.id}
                                        className={`relative pl-4 pb-3 ${index !== notes.length - 1 ? 'border-l border-border ml-1' : 'ml-1'}`}
                                    >
                                        <div className="absolute -left-1.5 top-0 h-3 w-3 rounded-full bg-primary/30 border-2 border-background" />
                                        
                                        <div className="bg-muted/30 rounded-lg p-3 hover:bg-muted/50 transition-colors">
                                            <div className="flex items-start justify-between gap-2 mb-1">
                                                <div className="flex-1 min-w-0">
                                                    <h4 className="text-xs font-medium truncate">
                                                        {note.title || '无标题笔记'}
                                                    </h4>
                                                    <div className="flex items-center gap-1 text-[10px] text-muted-foreground mt-0.5">
                                                        <Clock size={10} />
                                                        {format(new Date(note.updated_at), 'yyyy-MM-dd HH:mm', { locale: zhCN })}
                                                    </div>
                                                </div>
                                                <div className="flex gap-1">
                                                    <button
                                                        onClick={() => handleStartEditNote(note)}
                                                        className="p-1 hover:bg-background rounded text-muted-foreground hover:text-primary transition-colors"
                                                        title="编辑"
                                                    >
                                                        <Edit3 size={12} />
                                                    </button>
                                                    <button
                                                        onClick={() => handleDeleteNote(note.id)}
                                                        className="p-1 hover:bg-background rounded text-muted-foreground hover:text-red-500 transition-colors"
                                                        title="删除"
                                                    >
                                                        <Trash2 size={12} />
                                                    </button>
                                                </div>
                                            </div>
                                            
                                            {editingNote?.id === note.id ? null : (
                                                <>
                                                    <button
                                                        onClick={() => toggleNoteExpand(note.id)}
                                                        className="w-full text-left"
                                                    >
                                                        <div
                                                            className={`text-xs text-muted-foreground ${expandedNotes.has(note.id) ? '' : 'line-clamp-3'}`}
                                                            style={{ display: expandedNotes.has(note.id) ? 'block' : '-webkit-box', WebkitLineClamp: expandedNotes.has(note.id) ? 'unset' : 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}
                                                            dangerouslySetInnerHTML={{ __html: renderMarkdown(note.content) }}
                                                        />
                                                    </button>
                                                    {note.content.length > 100 && (
                                                        <button
                                                            onClick={() => toggleNoteExpand(note.id)}
                                                            className="text-[10px] text-primary hover:underline mt-1"
                                                        >
                                                            {expandedNotes.has(note.id) ? '收起' : '展开查看'}
                                                        </button>
                                                    )}
                                                </>
                                            )}
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
