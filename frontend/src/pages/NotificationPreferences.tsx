import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Settings, Bell, ArrowLeft, Save, TrendingUp, TrendingDown, Info } from 'lucide-react'
import {
    getNotificationPreferences,
    updateNotificationPreferences,
    NotificationPreference,
    NotificationTypeConfig,
} from '../lib/notifications'
import { useToast } from '../components/Toast'
import Loading from '../components/Loading'

export default function NotificationPreferences() {
    const { pushToast } = useToast()
    const queryClient = useQueryClient()
    const [localPrefs, setLocalPrefs] = useState<NotificationPreference[]>([])
    const [hasChanges, setHasChanges] = useState(false)

    const { data, isLoading } = useQuery({
        queryKey: ['notifications', 'preferences'],
        queryFn: getNotificationPreferences,
    })

    useEffect(() => {
        if (data) {
            setLocalPrefs(data.preferences)
        }
    }, [data])

    const mutation = useMutation({
        mutationFn: updateNotificationPreferences,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['notifications', 'preferences'] })
            setHasChanges(false)
            pushToast('设置已保存', 'success')
        },
        onError: () => pushToast('保存失败', 'error'),
    })

    const handleToggle = (type: string) => {
        setLocalPrefs((prev) =>
            prev.map((p) =>
                p.notification_type === type ? { ...p, enabled: !p.enabled } : p
            )
        )
        setHasChanges(true)
    }

    const handleThresholdChange = (
        type: string,
        field: 'threshold_up' | 'threshold_down',
        value: string
    ) => {
        const numValue = value === '' ? null : parseFloat(value)
        setLocalPrefs((prev) =>
            prev.map((p) =>
                p.notification_type === type ? { ...p, [field]: numValue } : p
            )
        )
        setHasChanges(true)
    }

    const handleSave = () => {
        mutation.mutate(localPrefs)
    }

    const handleReset = () => {
        if (data) {
            setLocalPrefs(data.preferences)
            setHasChanges(false)
        }
    }

    if (isLoading) return <Loading />

    const availableTypes = data?.available_types || []
    const typeConfigMap: Record<string, NotificationTypeConfig> = {}
    availableTypes.forEach((t) => {
        typeConfigMap[t.type] = t
    })

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <Link
                        to="/notifications"
                        className="p-2 rounded-lg hover:bg-muted transition-colors"
                    >
                        <ArrowLeft size={20} className="text-muted-foreground" />
                    </Link>
                    <div>
                        <h1 className="text-2xl font-bold text-foreground">通知设置</h1>
                        <p className="text-sm text-muted-foreground mt-1">
                            管理您的通知偏好和提醒阈值
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={handleReset}
                        disabled={!hasChanges || mutation.isPending}
                        className="px-4 py-2 rounded-xl border border-border hover:bg-muted transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        重置
                    </button>
                    <button
                        onClick={handleSave}
                        disabled={!hasChanges || mutation.isPending}
                        className="flex items-center gap-2 px-4 py-2 rounded-xl bg-primary text-white hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        <Save size={16} />
                        {mutation.isPending ? '保存中...' : '保存设置'}
                    </button>
                </div>
            </div>

            <div className="bg-card border border-border rounded-xl overflow-hidden">
                <div className="px-6 py-4 border-b border-border bg-muted/30">
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-primary/10 text-primary">
                            <Settings size={20} />
                        </div>
                        <div>
                            <h2 className="font-semibold text-foreground">通知类型</h2>
                            <p className="text-sm text-muted-foreground">
                                开启或关闭不同类型的通知推送
                            </p>
                        </div>
                    </div>
                </div>

                <div className="divide-y divide-border">
                    {localPrefs.map((pref) => {
                        const config = typeConfigMap[pref.notification_type]
                        if (!config) return null

                        return (
                            <div
                                key={pref.notification_type}
                                className={`p-6 transition-colors ${
                                    !pref.enabled ? 'opacity-60' : ''
                                }`}
                            >
                                <div className="flex items-start justify-between gap-6">
                                    <div className="flex-1">
                                        <div className="flex items-center gap-3 mb-1">
                                            <div
                                                className={`p-1.5 rounded-lg ${
                                                    pref.enabled
                                                        ? 'bg-primary/10 text-primary'
                                                        : 'bg-muted text-muted-foreground'
                                                }`}
                                            >
                                                <Bell size={14} />
                                            </div>
                                            <h3 className="font-medium text-foreground">
                                                {config.name}
                                            </h3>
                                        </div>
                                        <p className="text-sm text-muted-foreground ml-10">
                                            {config.description}
                                        </p>

                                        {config.has_threshold && pref.enabled && (
                                            <div className="mt-4 ml-10 grid grid-cols-1 md:grid-cols-2 gap-4">
                                                <div>
                                                    <label className="flex items-center gap-1.5 text-sm font-medium text-foreground mb-1.5">
                                                        <TrendingUp
                                                            size={14}
                                                            className="text-green-500"
                                                        />
                                                        上涨阈值 (%)
                                                    </label>
                                                    <div className="relative">
                                                        <input
                                                            type="number"
                                                            step="0.1"
                                                            min="0"
                                                            max="100"
                                                            value={
                                                                pref.threshold_up ?? ''
                                                            }
                                                            onChange={(e) =>
                                                                handleThresholdChange(
                                                                    pref.notification_type,
                                                                    'threshold_up',
                                                                    e.target.value
                                                                )
                                                            }
                                                            className="w-full px-3 py-2 pl-8 rounded-lg border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
                                                            placeholder="5.0"
                                                        />
                                                        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                                                            ≥
                                                        </span>
                                                    </div>
                                                    <p className="text-xs text-muted-foreground mt-1">
                                                        当涨幅达到此阈值时发送通知
                                                    </p>
                                                </div>
                                                <div>
                                                    <label className="flex items-center gap-1.5 text-sm font-medium text-foreground mb-1.5">
                                                        <TrendingDown
                                                            size={14}
                                                            className="text-red-500"
                                                        />
                                                        下跌阈值 (%)
                                                    </label>
                                                    <div className="relative">
                                                        <input
                                                            type="number"
                                                            step="0.1"
                                                            min="-100"
                                                            max="0"
                                                            value={
                                                                pref.threshold_down ?? ''
                                                            }
                                                            onChange={(e) =>
                                                                handleThresholdChange(
                                                                    pref.notification_type,
                                                                    'threshold_down',
                                                                    e.target.value
                                                                )
                                                            }
                                                            className="w-full px-3 py-2 pl-8 rounded-lg border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
                                                            placeholder="-5.0"
                                                        />
                                                        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                                                            ≤
                                                        </span>
                                                    </div>
                                                    <p className="text-xs text-muted-foreground mt-1">
                                                        当跌幅达到此阈值时发送通知
                                                    </p>
                                                </div>
                                            </div>
                                        )}
                                    </div>

                                    <div className="flex items-center shrink-0">
                                        <button
                                            onClick={() =>
                                                handleToggle(pref.notification_type)
                                            }
                                            className={`relative w-12 h-6 rounded-full transition-colors ${
                                                pref.enabled
                                                    ? 'bg-primary'
                                                    : 'bg-gray-300 dark:bg-gray-700'
                                            }`}
                                        >
                                            <span
                                                className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow-sm transition-transform ${
                                                    pref.enabled ? 'translate-x-6' : ''
                                                }`}
                                            />
                                        </button>
                                    </div>
                                </div>
                            </div>
                        )
                    })}
                </div>
            </div>

            <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-xl p-4">
                <div className="flex items-start gap-3">
                    <Info size={20} className="text-blue-500 shrink-0 mt-0.5" />
                    <div>
                        <h4 className="font-medium text-blue-900 dark:text-blue-300 mb-1">
                            关于通知
                        </h4>
                        <p className="text-sm text-blue-700 dark:text-blue-400">
                            通知会在系统发生重要事件时推送给您。您可以根据需要调整各类型通知的开关状态。
                            对于价格提醒，您可以自定义涨跌幅阈值，当自选股的价格变动达到您设置的阈值时，系统会自动发送通知。
                        </p>
                    </div>
                </div>
            </div>
        </div>
    )
}
