import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { format } from 'date-fns'
import { zhCN } from 'date-fns/locale'
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import {
    Bell,
    Check,
    Trash2,
    Settings,
    CheckCircle,
    AlertCircle,
    AlertTriangle,
    Info,
    ChevronLeft,
    ChevronRight,
    Filter,
    Inbox,
} from 'lucide-react'
import {
    getNotifications,
    markNotificationsRead,
    deleteNotifications,
    Notification,
    NOTIFICATION_TYPE_LABELS,
    SEVERITY_COLORS,
} from '../lib/notifications'
import { useToast } from '../components/Toast'
import Loading from '../components/Loading'

const severityIcons = {
    info: Info,
    success: CheckCircle,
    warning: AlertTriangle,
    error: AlertCircle,
}

const PAGE_SIZE = 20

export default function Notifications() {
    const [page, setPage] = useState(1)
    const [selectedIds, setSelectedIds] = useState<number[]>([])
    const [filters, setFilters] = useState({
        notification_type: '',
        is_read: '' as '' | 'true' | 'false',
        start_date: '',
        end_date: '',
    })
    const [showFilters, setShowFilters] = useState(false)

    const { pushToast } = useToast()
    const queryClient = useQueryClient()

    const queryParams = useMemo(() => {
        const params: Record<string, any> = {
            limit: PAGE_SIZE,
            offset: (page - 1) * PAGE_SIZE,
        }
        if (filters.notification_type) params.notification_type = filters.notification_type
        if (filters.is_read !== '') params.is_read = filters.is_read === 'true'
        if (filters.start_date) params.start_date = filters.start_date
        if (filters.end_date) params.end_date = filters.end_date
        return params
    }, [page, filters])

    const { data, isLoading, refetch } = useQuery({
        queryKey: ['notifications', 'list', queryParams],
        queryFn: () => getNotifications(queryParams),
    })

    const markReadMutation = useMutation({
        mutationFn: (ids: number[]) => markNotificationsRead(ids),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['notifications'] })
            setSelectedIds([])
            pushToast('已标记为已读', 'success')
        },
        onError: () => pushToast('操作失败', 'error'),
    })

    const markAllReadMutation = useMutation({
        mutationFn: () => markNotificationsRead(undefined, true),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['notifications'] })
            setSelectedIds([])
            pushToast('已全部标记为已读', 'success')
        },
        onError: () => pushToast('操作失败', 'error'),
    })

    const deleteMutation = useMutation({
        mutationFn: (ids: number[]) => deleteNotifications(ids),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['notifications'] })
            setSelectedIds([])
            pushToast('已删除', 'success')
        },
        onError: () => pushToast('操作失败', 'error'),
    })

    const handleSelectAll = () => {
        if (selectedIds.length === data?.items.length) {
            setSelectedIds([])
        } else {
            setSelectedIds(data?.items.map((n) => n.id) || [])
        }
    }

    const handleSelectOne = (id: number) => {
        setSelectedIds((prev) =>
            prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
        )
    }

    const handleMarkSelectedRead = () => {
        if (selectedIds.length > 0) {
            markReadMutation.mutate(selectedIds)
        }
    }

    const handleDeleteSelected = () => {
        if (selectedIds.length > 0 && window.confirm(`确定删除 ${selectedIds.length} 条通知？`)) {
            deleteMutation.mutate(selectedIds)
        }
    }

    const handleFilterChange = (key: keyof typeof filters, value: string) => {
        setFilters((prev) => ({ ...prev, [key]: value }))
        setPage(1)
    }

    const resetFilters = () => {
        setFilters({
            notification_type: '',
            is_read: '',
            start_date: '',
            end_date: '',
        })
        setPage(1)
    }

    const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0
    const notifications = data?.items || []
    const hasUnread = notifications.some((n) => !n.is_read)

    if (isLoading) return <Loading />

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-foreground">通知中心</h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        查看和管理所有系统通知
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    <button
                        onClick={() => setShowFilters(!showFilters)}
                        className={`flex items-center gap-2 px-4 py-2 rounded-xl border border-border hover:bg-muted transition-colors ${
                            showFilters ? 'bg-primary/10 border-primary/30' : ''
                        }`}
                    >
                        <Filter size={16} />
                        筛选
                    </button>
                    <Link
                        to="/notifications/preferences"
                        className="flex items-center gap-2 px-4 py-2 rounded-xl border border-border hover:bg-muted transition-colors"
                    >
                        <Settings size={16} />
                        通知设置
                    </Link>
                </div>
            </div>

            {showFilters && (
                <div className="bg-card border border-border rounded-xl p-4 space-y-4 animate-fade-in">
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-foreground mb-1.5">
                                通知类型
                            </label>
                            <select
                                value={filters.notification_type}
                                onChange={(e) =>
                                    handleFilterChange('notification_type', e.target.value)
                                }
                                className="w-full px-3 py-2 rounded-lg border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
                            >
                                <option value="">全部类型</option>
                                {Object.entries(NOTIFICATION_TYPE_LABELS).map(([value, label]) => (
                                    <option key={value} value={value}>
                                        {label}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-foreground mb-1.5">
                                已读状态
                            </label>
                            <select
                                value={filters.is_read}
                                onChange={(e) => handleFilterChange('is_read', e.target.value)}
                                className="w-full px-3 py-2 rounded-lg border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
                            >
                                <option value="">全部</option>
                                <option value="false">未读</option>
                                <option value="true">已读</option>
                            </select>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-foreground mb-1.5">
                                开始日期
                            </label>
                            <input
                                type="date"
                                value={filters.start_date}
                                onChange={(e) => handleFilterChange('start_date', e.target.value)}
                                className="w-full px-3 py-2 rounded-lg border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-foreground mb-1.5">
                                结束日期
                            </label>
                            <input
                                type="date"
                                value={filters.end_date}
                                onChange={(e) => handleFilterChange('end_date', e.target.value)}
                                className="w-full px-3 py-2 rounded-lg border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
                            />
                        </div>
                    </div>
                    <div className="flex justify-end">
                        <button
                            onClick={resetFilters}
                            className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
                        >
                            重置筛选
                        </button>
                    </div>
                </div>
            )}

            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <span className="text-sm text-muted-foreground">
                        共 {data?.total || 0} 条通知
                    </span>
                    {selectedIds.length > 0 && (
                        <span className="text-sm text-primary">
                            已选 {selectedIds.length} 条
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-2">
                    {hasUnread && (
                        <button
                            onClick={() => markAllReadMutation.mutate()}
                            disabled={markAllReadMutation.isPending}
                            className="flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg hover:bg-muted transition-colors disabled:opacity-50"
                        >
                            <Check size={14} />
                            全部已读
                        </button>
                    )}
                    {selectedIds.length > 0 && (
                        <>
                            <button
                                onClick={handleMarkSelectedRead}
                                disabled={markReadMutation.isPending}
                                className="flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg hover:bg-muted transition-colors disabled:opacity-50"
                            >
                                <Check size={14} />
                                标记已读
                            </button>
                            <button
                                onClick={handleDeleteSelected}
                                disabled={deleteMutation.isPending}
                                className="flex items-center gap-2 px-3 py-1.5 text-sm text-red-500 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors disabled:opacity-50"
                            >
                                <Trash2 size={14} />
                                删除
                            </button>
                        </>
                    )}
                </div>
            </div>

            {notifications.length === 0 ? (
                <div className="bg-card border border-border rounded-xl p-12 text-center">
                    <Inbox size={48} className="mx-auto mb-4 text-muted-foreground opacity-50" />
                    <p className="text-muted-foreground">暂无通知</p>
                </div>
            ) : (
                <div className="bg-card border border-border rounded-xl overflow-hidden">
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead>
                                <tr className="border-b border-border bg-muted/50">
                                    <th className="px-4 py-3 text-left w-12">
                                        <input
                                            type="checkbox"
                                            checked={
                                                selectedIds.length === notifications.length &&
                                                notifications.length > 0
                                            }
                                            onChange={handleSelectAll}
                                            className="h-4 w-4 rounded border-border text-primary focus:ring-primary"
                                        />
                                    </th>
                                    <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                                        类型
                                    </th>
                                    <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                                        标题
                                    </th>
                                    <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                                        状态
                                    </th>
                                    <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                                        时间
                                    </th>
                                    <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                                        操作
                                    </th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-border">
                                {notifications.map((notification) => (
                                    <NotificationRow
                                        key={notification.id}
                                        notification={notification}
                                        selected={selectedIds.includes(notification.id)}
                                        onSelect={() => handleSelectOne(notification.id)}
                                        onMarkRead={() => markReadMutation.mutate([notification.id])}
                                        onDelete={() => {
                                            if (window.confirm('确定删除这条通知？')) {
                                                deleteMutation.mutate([notification.id])
                                            }
                                        }}
                                    />
                                ))}
                            </tbody>
                        </table>
                    </div>

                    {totalPages > 1 && (
                        <div className="flex items-center justify-between px-4 py-3 border-t border-border">
                            <p className="text-sm text-muted-foreground">
                                第 {page} / {totalPages} 页
                            </p>
                            <div className="flex items-center gap-1">
                                <button
                                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                                    disabled={page === 1}
                                    className="p-2 rounded-lg hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                                >
                                    <ChevronLeft size={16} />
                                </button>
                                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                                    let pageNum = page - 2 + i
                                    if (pageNum < 1) pageNum = i + 1
                                    if (pageNum > totalPages) pageNum = totalPages - (4 - i)
                                    if (pageNum < 1 || pageNum > totalPages) return null
                                    return (
                                        <button
                                            key={pageNum}
                                            onClick={() => setPage(pageNum)}
                                            className={`w-8 h-8 rounded-lg text-sm font-medium transition-colors ${
                                                page === pageNum
                                                    ? 'bg-primary text-white'
                                                    : 'hover:bg-muted'
                                            }`}
                                        >
                                            {pageNum}
                                        </button>
                                    )
                                })}
                                <button
                                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                                    disabled={page === totalPages}
                                    className="p-2 rounded-lg hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                                >
                                    <ChevronRight size={16} />
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}

function NotificationRow({
    notification,
    selected,
    onSelect,
    onMarkRead,
    onDelete,
}: {
    notification: Notification
    selected: boolean
    onSelect: () => void
    onMarkRead: () => void
    onDelete: () => void
}) {
    const SeverityIcon = severityIcons[notification.severity] || Info

    return (
        <tr
            className={`transition-colors ${
                !notification.is_read ? 'bg-primary/5' : 'hover:bg-muted/50'
            } ${selected ? 'bg-primary/10' : ''}`}
        >
            <td className="px-4 py-3">
                <input
                    type="checkbox"
                    checked={selected}
                    onChange={onSelect}
                    className="h-4 w-4 rounded border-border text-primary focus:ring-primary"
                />
            </td>
            <td className="px-4 py-3">
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium bg-muted">
                    <SeverityIcon size={12} />
                    {NOTIFICATION_TYPE_LABELS[notification.type] || notification.type}
                </span>
            </td>
            <td className="px-4 py-3">
                <div className="flex items-start gap-3">
                    <div
                        className={`p-1.5 rounded-lg shrink-0 ${SEVERITY_COLORS[notification.severity]}`}
                    >
                        <SeverityIcon size={14} />
                    </div>
                    <div className="min-w-0">
                        <p
                            className={`text-sm ${
                                !notification.is_read ? 'font-semibold' : 'font-medium'
                            } text-foreground`}
                        >
                            {notification.title}
                        </p>
                        {notification.content && (
                            <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                                {notification.content}
                            </p>
                        )}
                    </div>
                </div>
            </td>
            <td className="px-4 py-3">
                <span
                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs ${
                        notification.is_read
                            ? 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'
                            : 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                    }`}
                >
                    {notification.is_read ? '已读' : '未读'}
                </span>
            </td>
            <td className="px-4 py-3 text-sm text-muted-foreground whitespace-nowrap">
                {format(new Date(notification.created_at), 'yyyy-MM-dd HH:mm', {
                    locale: zhCN,
                })}
            </td>
            <td className="px-4 py-3 text-right">
                <div className="flex items-center justify-end gap-1">
                    {!notification.is_read && (
                        <button
                            onClick={onMarkRead}
                            className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                            title="标记已读"
                        >
                            <Check size={14} />
                        </button>
                    )}
                    <button
                        onClick={onDelete}
                        className="p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 text-muted-foreground hover:text-red-500 transition-colors"
                        title="删除"
                    >
                        <Trash2 size={14} />
                    </button>
                </div>
            </td>
        </tr>
    )
}
