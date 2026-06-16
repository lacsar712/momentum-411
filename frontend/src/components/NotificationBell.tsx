import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell, X, CheckCircle, AlertCircle, AlertTriangle, Info, ChevronRight } from 'lucide-react'
import { format } from 'date-fns'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
    getNotifications,
    getUnreadCount,
    markNotificationsRead,
    Notification,
    NOTIFICATION_TYPE_LABELS,
    SEVERITY_COLORS,
} from '../lib/notifications'
import { useToast } from './Toast'
import { zhCN } from 'date-fns/locale'

const severityIcons = {
    info: Info,
    success: CheckCircle,
    warning: AlertTriangle,
    error: AlertCircle,
}

export default function NotificationBell() {
    const [open, setOpen] = useState(false)
    const bellRef = useRef<HTMLDivElement>(null)
    const navigate = useNavigate()
    const { pushToast } = useToast()
    const queryClient = useQueryClient()

    const { data: unreadData } = useQuery({
        queryKey: ['notifications', 'unread'],
        queryFn: getUnreadCount,
        refetchInterval: 30000,
    })

    const { data: recentData, isLoading } = useQuery({
        queryKey: ['notifications', 'recent'],
        queryFn: () => getNotifications({ limit: 5, is_read: false }),
        enabled: open,
    })

    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            if (bellRef.current && !bellRef.current.contains(e.target as Node)) {
                setOpen(false)
            }
        }
        document.addEventListener('mousedown', handleClickOutside)
        return () => document.removeEventListener('mousedown', handleClickOutside)
    }, [])

    const handleNotificationClick = async (notification: Notification) => {
        try {
            await markNotificationsRead([notification.id])
            queryClient.invalidateQueries({ queryKey: ['notifications'] })
        } catch {
            pushToast('标记已读失败', 'error')
        }
        if (notification.link_url) {
            navigate(notification.link_url)
        }
        setOpen(false)
    }

    const handleMarkAllRead = async () => {
        try {
            await markNotificationsRead(undefined, true)
            queryClient.invalidateQueries({ queryKey: ['notifications'] })
            pushToast('已全部标记为已读', 'success')
        } catch {
            pushToast('操作失败', 'error')
        }
    }

    const handleViewAll = () => {
        setOpen(false)
        navigate('/notifications')
    }

    const unreadCount = unreadData?.unread_count || 0
    const notifications = recentData?.items || []

    return (
        <div className="relative" ref={bellRef}>
            <button
                onClick={() => setOpen(!open)}
                className="relative p-2 rounded-xl hover:bg-muted transition-colors"
            >
                <Bell size={20} className="text-muted-foreground" />
                {unreadCount > 0 && (
                    <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] flex items-center justify-center bg-red-500 text-white text-[10px] font-medium rounded-full px-1 animate-pulse">
                        {unreadCount > 99 ? '99+' : unreadCount}
                    </span>
                )}
            </button>

            {open && (
                <div className="absolute right-0 top-full mt-2 w-96 bg-card border border-border rounded-xl shadow-lg z-50 animate-slide-down overflow-hidden">
                    <div className="flex items-center justify-between px-4 py-3 border-b border-border">
                        <h3 className="font-semibold text-foreground">通知中心</h3>
                        <div className="flex items-center gap-2">
                            {unreadCount > 0 && (
                                <button
                                    onClick={handleMarkAllRead}
                                    className="text-xs text-primary hover:text-primary/80 transition-colors"
                                >
                                    全部已读
                                </button>
                            )}
                            <button
                                onClick={() => setOpen(false)}
                                className="p-1 hover:bg-muted rounded-lg transition-colors"
                            >
                                <X size={14} className="text-muted-foreground" />
                            </button>
                        </div>
                    </div>

                    <div className="max-h-96 overflow-y-auto">
                        {isLoading ? (
                            <div className="p-8 text-center text-muted-foreground">
                                <div className="animate-spin w-6 h-6 border-2 border-primary border-t-transparent rounded-full mx-auto mb-2" />
                                加载中...
                            </div>
                        ) : notifications.length === 0 ? (
                            <div className="p-8 text-center text-muted-foreground">
                                <Bell size={32} className="mx-auto mb-2 opacity-50" />
                                <p className="text-sm">暂无未读通知</p>
                            </div>
                        ) : (
                            <div>
                                {notifications.map((notification) => {
                                    const SeverityIcon = severityIcons[notification.severity] || Info
                                    return (
                                        <div
                                            key={notification.id}
                                            onClick={() => handleNotificationClick(notification)}
                                            className={`flex items-start gap-3 px-4 py-3 hover:bg-muted cursor-pointer transition-colors border-b border-border last:border-b-0 ${
                                                !notification.is_read ? 'bg-primary/5' : ''
                                            }`}
                                        >
                                            <div
                                                className={`p-2 rounded-lg shrink-0 ${SEVERITY_COLORS[notification.severity]}`}
                                            >
                                                <SeverityIcon size={16} />
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center justify-between gap-2 mb-0.5">
                                                    <span className="text-xs text-muted-foreground">
                                                        {NOTIFICATION_TYPE_LABELS[notification.type] ||
                                                            notification.type}
                                                    </span>
                                                    <span className="text-xs text-muted-foreground shrink-0">
                                                        {format(
                                                            new Date(notification.created_at),
                                                            'MM-dd HH:mm',
                                                            { locale: zhCN }
                                                        )}
                                                    </span>
                                                </div>
                                                <p className="text-sm font-medium text-foreground truncate">
                                                    {notification.title}
                                                </p>
                                                {notification.content && (
                                                    <p className="text-xs text-muted-foreground line-clamp-2 mt-0.5">
                                                        {notification.content}
                                                    </p>
                                                )}
                                            </div>
                                            {notification.link_url && (
                                                <ChevronRight
                                                    size={14}
                                                    className="text-muted-foreground shrink-0 mt-2"
                                                />
                                            )}
                                        </div>
                                    )
                                })}
                            </div>
                        )}
                    </div>

                    <div className="px-4 py-3 border-t border-border">
                        <button
                            onClick={handleViewAll}
                            className="w-full text-center text-sm text-primary hover:text-primary/80 font-medium transition-colors"
                        >
                            查看全部通知
                        </button>
                    </div>
                </div>
            )}
        </div>
    )
}
