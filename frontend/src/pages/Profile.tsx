import { useState, useEffect, useRef, ChangeEvent } from 'react'
import { User, Lock, History, Camera, Check, X, Eye, EyeOff } from 'lucide-react'
import { useAuth } from '../lib/auth'
import { api } from '../lib/api'
import { useToast } from '../components/Toast'
import Loading from '../components/Loading'
import DatePicker from '../components/DatePicker'
import { AxiosResponse } from 'axios'

type TabType = 'info' | 'password' | 'logs'

interface ActivityLogItem {
    id: number
    action_type: string
    action_detail: string | null
    ip_address: string | null
    created_at: string
}

interface ActivityLogResponse {
    total: number
    items: ActivityLogItem[]
}

const ActionTypeMap: Record<string, { label: string; color: string }> = {
    login: { label: '登录', color: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' },
    logout: { label: '退出', color: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-400' },
    change_password: { label: '修改密码', color: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400' },
    save_preset: { label: '保存方案', color: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' },
    run_backtest: { label: '运行回测', color: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400' },
    run_screening: { label: '运行选股', color: 'bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-400' },
    run_sync: { label: '数据同步', color: 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400' },
    pattern_scan: { label: '形态扫描', color: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400' },
    upload_avatar: { label: '上传头像', color: 'bg-pink-100 text-pink-700 dark:bg-pink-900/30 dark:text-pink-400' },
    update_preferences: { label: '更新偏好', color: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400' },
}

const tabs: { key: TabType; label: string; icon: typeof User }[] = [
    { key: 'info', label: '基本信息', icon: User },
    { key: 'password', label: '修改密码', icon: Lock },
    { key: 'logs', label: '操作日志', icon: History },
]

export default function Profile() {
    const { user, isAdmin, fetchUser, loading: authLoading } = useAuth()
    const { pushToast } = useToast()
    const [activeTab, setActiveTab] = useState<TabType>('info')
    const fileInputRef = useRef<HTMLInputElement>(null)

    const [oldPassword, setOldPassword] = useState('')
    const [newPassword, setNewPassword] = useState('')
    const [confirmPassword, setConfirmPassword] = useState('')
    const [showOldPassword, setShowOldPassword] = useState(false)
    const [showNewPassword, setShowNewPassword] = useState(false)
    const [showConfirmPassword, setShowConfirmPassword] = useState(false)
    const [passwordLoading, setPasswordLoading] = useState(false)
    const [passwordStrength, setPasswordStrength] = useState({ score: 0, level: 'weak', feedback: [] as string[], passed: false })

    const [logs, setLogs] = useState<ActivityLogItem[]>([])
    const [logsLoading, setLogsLoading] = useState(false)
    const [logsTotal, setLogsTotal] = useState(0)
    const [logsPage, setLogsPage] = useState(1)
    const [actionTypeFilter, setActionTypeFilter] = useState('')
    const [startDate, setStartDate] = useState('')
    const [endDate, setEndDate] = useState('')
    const pageSize = 20

    const [avatarUploading, setAvatarUploading] = useState(false)

    const displayName = user?.username === 'admin' ? '管理员' : user?.username === 'analyst' ? '分析师' : user?.username || '用户'
    const roleLabel = isAdmin ? '超级管理员' : '数据分析师'

    useEffect(() => {
        if (newPassword) {
            api.get('/auth/password_strength', { params: { password: newPassword } })
                .then((res) => setPasswordStrength(res.data))
        } else {
            setPasswordStrength({ score: 0, level: 'weak', feedback: [], passed: false })
        }
    }, [newPassword])

    useEffect(() => {
        if (activeTab === 'logs') {
            fetchLogs()
        }
    }, [activeTab, logsPage, actionTypeFilter, startDate, endDate])

    const fetchLogs = () => {
        setLogsLoading(true)
        api.get('/auth/activity_log', {
            params: {
                limit: pageSize,
                offset: (logsPage - 1) * pageSize,
                action_type: actionTypeFilter || undefined,
                start_date: startDate || undefined,
                end_date: endDate || undefined,
            },
        })
            .then((res: AxiosResponse<ActivityLogResponse>) => {
                setLogs(res.data.items)
                setLogsTotal(res.data.total)
            })
            .catch(() => pushToast('加载操作日志失败', 'error'))
            .finally(() => setLogsLoading(false))
    }

    const handleAvatarUpload = (e: ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (!file) return

        if (!file.type.startsWith('image/')) {
            pushToast('请选择图片文件', 'error')
            return
        }

        setAvatarUploading(true)
        const formData = new FormData()
        formData.append('file', file)

        api.post('/auth/avatar', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        })
            .then(() => {
                pushToast('头像上传成功', 'success')
                fetchUser()
            })
            .catch(() => pushToast('头像上传失败', 'error'))
            .finally(() => {
                setAvatarUploading(false)
                if (fileInputRef.current) fileInputRef.current.value = ''
            })
    }

    const handleChangePassword = () => {
        if (!oldPassword || !newPassword || !confirmPassword) {
            pushToast('请填写所有密码字段', 'error')
            return
        }
        if (newPassword !== confirmPassword) {
            pushToast('两次输入的新密码不一致', 'error')
            return
        }
        if (!passwordStrength.passed) {
            pushToast('密码强度不足', 'error')
            return
        }

        setPasswordLoading(true)
        api.post('/auth/change_password', {
            old_password: oldPassword,
            new_password: newPassword,
        })
            .then(() => {
                pushToast('密码修改成功，请重新登录', 'success')
                setOldPassword('')
                setNewPassword('')
                setConfirmPassword('')
                setTimeout(() => {
                    localStorage.removeItem('momentum_token')
                    localStorage.removeItem('momentum_role')
                    window.dispatchEvent(new Event('momentum-auth'))
                    window.location.href = '/login'
                }, 1500)
            })
            .catch((err) => {
                const msg = err.response?.data?.detail?.message || err.response?.data?.detail || '密码修改失败'
                pushToast(msg, 'error')
            })
            .finally(() => setPasswordLoading(false))
    }

    const totalPages = Math.ceil(logsTotal / pageSize)

    const getStrengthColor = () => {
        switch (passwordStrength.level) {
            case 'strong': return 'bg-emerald-500'
            case 'medium': return 'bg-amber-500'
            default: return 'bg-rose-500'
        }
    }

    const getStrengthText = () => {
        switch (passwordStrength.level) {
            case 'strong': return '强'
            case 'medium': return '中'
            default: return '弱'
        }
    }

    if (authLoading) {
        return <div className="p-8"><Loading /></div>
    }

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-2xl font-semibold">个人中心</h2>
                <p className="text-sm text-muted-foreground">管理您的账户信息与偏好设置</p>
            </div>

            <div className="glass-card rounded-2xl overflow-hidden">
                <div className="flex border-b border-border">
                    {tabs.map((tab) => {
                        const Icon = tab.icon
                        return (
                            <button
                                key={tab.key}
                                onClick={() => setActiveTab(tab.key)}
                                className={`flex items-center gap-2 px-6 py-4 text-sm font-medium transition-colors border-b-2 -mb-px ${
                                    activeTab === tab.key
                                        ? 'text-primary border-primary'
                                        : 'text-muted-foreground border-transparent hover:text-foreground'
                                }`}
                            >
                                <Icon size={16} />
                                {tab.label}
                            </button>
                        )
                    })}
                </div>

                <div className="p-6">
                    {activeTab === 'info' && (
                        <div className="space-y-6">
                            <div className="flex items-start gap-6">
                                <div className="relative group">
                                    <div className={`h-24 w-24 rounded-full flex items-center justify-center ring-2 shadow-md ${isAdmin ? 'bg-primary/10 ring-primary/30 text-primary' : 'bg-emerald-50 ring-emerald-200 text-emerald-600 dark:bg-emerald-900/30 dark:ring-emerald-800 dark:text-emerald-400'}`}>
                                        {user?.avatar_url ? (
                                            <img src={user.avatar_url} alt="" className="h-24 w-24 rounded-full object-cover" />
                                        ) : (
                                            <User size={40} />
                                        )}
                                    </div>
                                    <button
                                        onClick={() => fileInputRef.current?.click()}
                                        className="absolute bottom-0 right-0 h-8 w-8 rounded-full bg-primary text-primary-foreground flex items-center justify-center shadow-lg opacity-0 group-hover:opacity-100 transition-opacity"
                                        disabled={avatarUploading}
                                    >
                                        {avatarUploading ? (
                                            <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                            </svg>
                                        ) : (
                                            <Camera size={14} />
                                        )}
                                    </button>
                                    <input
                                        ref={fileInputRef}
                                        type="file"
                                        accept="image/*"
                                        className="hidden"
                                        onChange={handleAvatarUpload}
                                    />
                                </div>
                                <div className="flex-1 space-y-1">
                                    <h3 className="text-lg font-semibold">{displayName}</h3>
                                    <p className="text-sm text-muted-foreground">{roleLabel}</p>
                                    <p className="text-xs text-muted-foreground mt-2">点击右下角相机图标可更换头像</p>
                                </div>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-border">
                                <div>
                                    <label className="text-xs text-muted-foreground">用户名</label>
                                    <div className="mt-1 px-3 py-2 rounded-lg bg-muted/50 text-sm">{user?.username}</div>
                                </div>
                                <div>
                                    <label className="text-xs text-muted-foreground">用户角色</label>
                                    <div className="mt-1 px-3 py-2 rounded-lg bg-muted/50 text-sm">{roleLabel}</div>
                                </div>
                                <div>
                                    <label className="text-xs text-muted-foreground">注册时间</label>
                                    <div className="mt-1 px-3 py-2 rounded-lg bg-muted/50 text-sm">
                                        {user?.created_at ? new Date(user.created_at).toLocaleString('zh-CN') : '-'}
                                    </div>
                                </div>
                                <div>
                                    <label className="text-xs text-muted-foreground">最近登录</label>
                                    <div className="mt-1 px-3 py-2 rounded-lg bg-muted/50 text-sm">
                                        {user?.last_login ? new Date(user.last_login).toLocaleString('zh-CN') : '-'}
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {activeTab === 'password' && (
                        <div className="max-w-md space-y-5">
                            <div>
                                <label className="text-xs text-muted-foreground">当前密码</label>
                                <div className="mt-1 relative">
                                    <input
                                        type={showOldPassword ? 'text' : 'password'}
                                        value={oldPassword}
                                        onChange={(e) => setOldPassword(e.target.value)}
                                        className="w-full rounded-lg border border-border px-3 py-2 text-sm pr-10 focus:outline-none focus:ring-2 focus:ring-primary/50"
                                        placeholder="请输入当前密码"
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowOldPassword(!showOldPassword)}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                                    >
                                        {showOldPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                                    </button>
                                </div>
                            </div>

                            <div>
                                <label className="text-xs text-muted-foreground">新密码</label>
                                <div className="mt-1 relative">
                                    <input
                                        type={showNewPassword ? 'text' : 'password'}
                                        value={newPassword}
                                        onChange={(e) => setNewPassword(e.target.value)}
                                        className="w-full rounded-lg border border-border px-3 py-2 text-sm pr-10 focus:outline-none focus:ring-2 focus:ring-primary/50"
                                        placeholder="请输入新密码"
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowNewPassword(!showNewPassword)}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                                    >
                                        {showNewPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                                    </button>
                                </div>
                                {newPassword && (
                                    <div className="mt-2 space-y-2">
                                        <div className="flex items-center gap-2">
                                            <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
                                                <div
                                                    className={`h-full transition-all duration-300 ${getStrengthColor()}`}
                                                    style={{ width: `${(passwordStrength.score / 5) * 100}%` }}
                                                />
                                            </div>
                                            <span className={`text-xs font-medium ${
                                                passwordStrength.level === 'strong' ? 'text-emerald-600 dark:text-emerald-400' :
                                                passwordStrength.level === 'medium' ? 'text-amber-600 dark:text-amber-400' :
                                                'text-rose-600 dark:text-rose-400'
                                            }`}>
                                                强度: {getStrengthText()}
                                            </span>
                                        </div>
                                        <div className="space-y-1">
                                            <p className="text-xs font-medium text-muted-foreground">密码规则：</p>
                                            {['至少 8 位', '包含小写字母', '包含大写字母', '包含数字', '包含特殊字符'].map((rule, i) => {
                                                const isActuallyPassed = i === 0 ? newPassword.length >= 8 :
                                                    i === 1 ? /[a-z]/.test(newPassword) :
                                                    i === 2 ? /[A-Z]/.test(newPassword) :
                                                    i === 3 ? /[0-9]/.test(newPassword) :
                                                    /[!@#$%^&*(),.?":{}|<>]/.test(newPassword)
                                                return (
                                                    <div key={i} className={`flex items-center gap-2 text-xs ${isActuallyPassed ? 'text-emerald-600 dark:text-emerald-400' : 'text-muted-foreground'}`}>
                                                        {isActuallyPassed ? <Check size={12} /> : <X size={12} />}
                                                        {rule}
                                                    </div>
                                                )
                                            })}
                                        </div>
                                    </div>
                                )}
                            </div>

                            <div>
                                <label className="text-xs text-muted-foreground">确认新密码</label>
                                <div className="mt-1 relative">
                                    <input
                                        type={showConfirmPassword ? 'text' : 'password'}
                                        value={confirmPassword}
                                        onChange={(e) => setConfirmPassword(e.target.value)}
                                        className={`w-full rounded-lg border px-3 py-2 text-sm pr-10 focus:outline-none focus:ring-2 focus:ring-primary/50 ${
                                            confirmPassword && newPassword !== confirmPassword ? 'border-destructive' : 'border-border'
                                        }`}
                                        placeholder="请再次输入新密码"
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                                    >
                                        {showConfirmPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                                    </button>
                                </div>
                                {confirmPassword && newPassword !== confirmPassword && (
                                    <p className="mt-1 text-xs text-destructive">两次输入的密码不一致</p>
                                )}
                            </div>

                            <button
                                onClick={handleChangePassword}
                                disabled={passwordLoading || !oldPassword || !newPassword || !confirmPassword || newPassword !== confirmPassword || !passwordStrength.passed}
                                className="w-full rounded-xl bg-primary px-4 py-2.5 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                            >
                                {passwordLoading && (
                                    <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                    </svg>
                                )}
                                修改密码
                            </button>
                        </div>
                    )}

                    {activeTab === 'logs' && (
                        <div className="space-y-4">
                            <div className="flex flex-wrap gap-3 items-end">
                                <div className="w-40">
                                    <label className="text-xs text-muted-foreground">操作类型</label>
                                    <select
                                        value={actionTypeFilter}
                                        onChange={(e) => { setActionTypeFilter(e.target.value); setLogsPage(1) }}
                                        className="mt-1 w-full rounded-lg border border-border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 bg-background"
                                    >
                                        <option value="">全部类型</option>
                                        {Object.entries(ActionTypeMap).map(([key, val]) => (
                                            <option key={key} value={key}>{val.label}</option>
                                        ))}
                                    </select>
                                </div>
                                <div className="w-40">
                                    <label className="text-xs text-muted-foreground">开始日期</label>
                                    <DatePicker value={startDate} onChange={(d) => { setStartDate(d); setLogsPage(1) }} placeholder="选择日期" />
                                </div>
                                <div className="w-40">
                                    <label className="text-xs text-muted-foreground">结束日期</label>
                                    <DatePicker value={endDate} onChange={(d) => { setEndDate(d); setLogsPage(1) }} placeholder="选择日期" />
                                </div>
                                <button
                                    onClick={() => { setActionTypeFilter(''); setStartDate(''); setEndDate(''); setLogsPage(1) }}
                                    className="rounded-lg border border-border px-4 py-2 text-sm hover:bg-muted transition-colors"
                                >
                                    重置筛选
                                </button>
                            </div>

                            {logsLoading ? (
                                <div className="p-8"><Loading /></div>
                            ) : (
                                <>
                                    <div className="border border-border rounded-xl overflow-hidden">
                                        <table className="min-w-full text-left text-sm">
                                            <thead className="bg-muted text-muted-foreground">
                                                <tr>
                                                    <th className="px-4 py-3 font-medium">时间</th>
                                                    <th className="px-4 py-3 font-medium">操作类型</th>
                                                    <th className="px-4 py-3 font-medium">操作详情</th>
                                                    <th className="px-4 py-3 font-medium">IP 地址</th>
                                                </tr>
                                            </thead>
                                            <tbody className="divide-y divide-border">
                                                {logs.map((log) => {
                                                    const typeInfo = ActionTypeMap[log.action_type] || { label: log.action_type, color: 'bg-slate-100 text-slate-700' }
                                                    return (
                                                        <tr key={log.id} className="hover:bg-muted/50">
                                                            <td className="px-4 py-3 whitespace-nowrap text-muted-foreground">
                                                                {new Date(log.created_at).toLocaleString('zh-CN')}
                                                            </td>
                                                            <td className="px-4 py-3">
                                                                <span className={`inline-flex px-2.5 py-1 rounded-full text-xs font-medium ${typeInfo.color}`}>
                                                                    {typeInfo.label}
                                                                </span>
                                                            </td>
                                                            <td className="px-4 py-3 max-w-md truncate text-foreground" title={log.action_detail || ''}>
                                                                {log.action_detail || '-'}
                                                            </td>
                                                            <td className="px-4 py-3 text-muted-foreground text-xs font-mono">
                                                                {log.ip_address || '-'}
                                                            </td>
                                                        </tr>
                                                    )
                                                })}
                                                {logs.length === 0 && (
                                                    <tr>
                                                        <td colSpan={4} className="px-4 py-8 text-center text-muted-foreground">暂无操作记录</td>
                                                    </tr>
                                                )}
                                            </tbody>
                                        </table>
                                    </div>

                                    <div className="flex items-center justify-between">
                                        <div className="text-xs text-muted-foreground">
                                            共 {logsTotal} 条记录，第 {logsPage} / {totalPages || 1} 页
                                        </div>
                                        <div className="flex gap-2">
                                            <button
                                                disabled={logsPage <= 1}
                                                onClick={() => setLogsPage((p) => Math.max(1, p - 1))}
                                                className="rounded-lg border border-border px-3 py-1.5 text-xs disabled:opacity-50 hover:bg-muted transition-colors"
                                            >
                                                上一页
                                            </button>
                                            <button
                                                disabled={logsPage >= totalPages}
                                                onClick={() => setLogsPage((p) => p + 1)}
                                                className="rounded-lg border border-border px-3 py-1.5 text-xs disabled:opacity-50 hover:bg-muted transition-colors"
                                            >
                                                下一页
                                            </button>
                                        </div>
                                    </div>
                                </>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
