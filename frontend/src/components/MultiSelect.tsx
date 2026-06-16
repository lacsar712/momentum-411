import { useState, useRef, useEffect } from 'react'
import { ChevronDown, Search, Check, X } from 'lucide-react'

interface MultiSelectOption {
    value: string
    label: string
}

interface MultiSelectProps {
    value: string[]
    options: MultiSelectOption[]
    onChange: (value: string[]) => void
    placeholder?: string
    searchable?: boolean
    maxDisplay?: number
    disabled?: boolean
}

export default function MultiSelect({
    value,
    options,
    onChange,
    placeholder = '请选择',
    searchable = true,
    maxDisplay = 3,
    disabled = false,
}: MultiSelectProps) {
    const [open, setOpen] = useState(false)
    const [search, setSearch] = useState('')
    const ref = useRef<HTMLDivElement>(null)

    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (ref.current && !ref.current.contains(event.target as Node)) {
                setOpen(false)
            }
        }
        document.addEventListener('mousedown', handleClickOutside)
        return () => document.removeEventListener('mousedown', handleClickOutside)
    }, [])

    const filtered = options.filter(o => {
        if (!search) return true
        const s = search.toLowerCase()
        return o.value.toLowerCase().includes(s) || o.label.toLowerCase().includes(s)
    })

    const selectedSet = new Set(value)
    const selectedOptions = options.filter(o => selectedSet.has(o.value))

    const toggleOption = (optValue: string) => {
        if (selectedSet.has(optValue)) {
            onChange(value.filter(v => v !== optValue))
        } else {
            onChange([...value, optValue])
        }
    }

    const removeOption = (optValue: string, e: React.MouseEvent) => {
        e.stopPropagation()
        onChange(value.filter(v => v !== optValue))
    }

    const clearAll = (e: React.MouseEvent) => {
        e.stopPropagation()
        onChange([])
    }

    const renderDisplay = () => {
        if (selectedOptions.length === 0) {
            return <span className="text-slate-400">{placeholder}</span>
        }
        if (selectedOptions.length <= maxDisplay) {
            return (
                <div className="flex flex-wrap gap-1.5 items-center flex-1 min-w-0">
                    {selectedOptions.map(opt => (
                        <span
                            key={opt.value}
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-primary/10 text-primary text-xs font-medium"
                        >
                            <span className="truncate max-w-[120px]">{opt.label}</span>
                            {!disabled && (
                                <button
                                    onClick={(e) => removeOption(opt.value, e)}
                                    className="hover:bg-primary/20 rounded p-0.5 -mr-0.5 transition-colors"
                                >
                                    <X size={10} />
                                </button>
                            )}
                        </span>
                    ))}
                </div>
            )
        }
        const restCount = selectedOptions.length - maxDisplay
        return (
            <div className="flex flex-wrap gap-1.5 items-center flex-1 min-w-0">
                {selectedOptions.slice(0, maxDisplay).map(opt => (
                    <span
                        key={opt.value}
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-primary/10 text-primary text-xs font-medium"
                    >
                        <span className="truncate max-w-[100px]">{opt.label}</span>
                        {!disabled && (
                            <button
                                onClick={(e) => removeOption(opt.value, e)}
                                className="hover:bg-primary/20 rounded p-0.5 -mr-0.5 transition-colors"
                            >
                                <X size={10} />
                            </button>
                        )}
                    </span>
                ))}
                <span className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 text-xs font-medium">
                    +{restCount} 已选
                </span>
            </div>
        )
    }

    return (
        <div className="relative" ref={ref}>
            <button
                type="button"
                disabled={disabled}
                onClick={() => !disabled && setOpen(!open)}
                className={`
                    w-full flex items-center justify-between gap-2
                    px-3 py-2.5 rounded-xl
                    bg-white border-2 border-slate-200
                    text-sm font-medium
                    transition-all duration-200
                    hover:border-primary/50 hover:shadow-sm
                    focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20
                    ${open ? 'border-primary ring-2 ring-primary/20 shadow-sm' : ''}
                    ${disabled ? 'opacity-50 cursor-not-allowed bg-slate-50' : 'cursor-pointer'}
                `}
            >
                <div className="flex-1 min-w-0 text-left">
                    {renderDisplay()}
                </div>
                <div className="flex items-center gap-1 shrink-0">
                    {selectedOptions.length > 0 && !disabled && (
                        <button
                            onClick={clearAll}
                            className="p-1 rounded text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
                        >
                            <X size={14} />
                        </button>
                    )}
                    <ChevronDown
                        size={16}
                        className={`text-slate-400 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
                    />
                </div>
            </button>

            {open && (
                <div className="absolute top-full left-0 right-0 mt-2 z-50 overflow-hidden rounded-xl bg-white border-2 border-slate-200 shadow-xl animate-in fade-in slide-in-from-top-2 duration-200">
                    {searchable && (
                        <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-100 bg-slate-50/50">
                            <Search size={16} className="text-slate-400 shrink-0" />
                            <input
                                autoFocus
                                className="flex-1 bg-transparent text-sm outline-none placeholder:text-slate-400 min-w-0"
                                placeholder="搜索代码或名称..."
                                value={search}
                                onChange={e => setSearch(e.target.value)}
                            />
                        </div>
                    )}
                    <div className="max-h-[280px] overflow-y-auto p-1.5">
                        {filtered.length === 0 ? (
                            <div className="px-4 py-8 text-center text-sm text-slate-400">
                                未找到匹配项
                            </div>
                        ) : (
                            filtered.map(option => {
                                const isSelected = selectedSet.has(option.value)
                                return (
                                    <button
                                        key={option.value}
                                        onClick={() => toggleOption(option.value)}
                                        className={`
                                            w-full flex items-center justify-between gap-2
                                            px-3 py-2.5 rounded-lg text-sm
                                            transition-all duration-150
                                            ${isSelected
                                                ? 'bg-primary/10 text-primary font-medium'
                                                : 'text-slate-700 hover:bg-slate-100'
                                            }
                                        `}
                                    >
                                        <span className="truncate text-left">{option.label}</span>
                                        {isSelected && <Check size={16} className="text-primary shrink-0" />}
                                    </button>
                                )
                            })
                        )}
                    </div>
                    {options.length > 0 && (
                        <div className="px-4 py-2.5 border-t border-slate-100 bg-slate-50/50 flex items-center justify-between">
                            <span className="text-xs text-slate-500">
                                已选 {selectedOptions.length} / {options.length}
                            </span>
                            {selectedOptions.length > 0 && (
                                <button
                                    onClick={() => onChange([])}
                                    className="text-xs text-primary hover:text-primary/80 font-medium"
                                >
                                    清空选择
                                </button>
                            )}
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}
