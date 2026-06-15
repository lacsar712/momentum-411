import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { User, Settings, LogOut, Moon, Sun, ChevronDown } from 'lucide-react'
import { useAuth } from '../lib/auth'
import { useToast } from './Toast'

export default function UserMenu() {
    const { user, isAdmin, preferences, updatePreferences } = useAuth()
    const { pushToast } = useToast()
    const navigate = useNavigate()
    const [open, setOpen] = useState(false)
    const menuRef = useRef<HTMLDivElement>(null)

    const displayName = user?.username === 'admin' ? '管理员' : user?.username === 'analyst' ? '分析师' : user?.username || '用户'
    const roleLabel = isAdmin ? '超级管理员' : '数据分析师'
    const isDark = preferences.theme === 'dark'

    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
                setOpen(false)
            }
        }
        document.addEventListener('mousedown', handleClickOutside)
        return () => document.removeEventListener('mousedown', handleClickOutside)
    }, [])

    useEffect(() => {
        if (preferences.theme === 'dark') {
            document.documentElement.classList.add('dark')
        } else {
            document.documentElement.classList.remove('dark')
        }
    }, [preferences.theme])

    const handleToggleTheme = async () => {
        const newTheme = isDark ? 'light' : 'dark'
        try {
            await updatePreferences({ theme: newTheme })
            pushToast(`已切换到${newTheme === 'dark' ? '暗色' : '亮色'}模式`, 'success')
        } catch {
            pushToast('切换主题失败', 'error')
        }
    }

    const handleLogout = () => {
        localStorage.removeItem('momentum_token')
        localStorage.removeItem('momentum_role')
        window.dispatchEvent(new Event('momentum-auth'))
        navigate('/login')
        pushToast('已退出登录', 'success')
    }

    const handleProfile = () => {
        setOpen(false)
        navigate('/profile')
    }

    return (
        <div className="relative" ref={menuRef}>
            <button
                onClick={() => setOpen(!open)}
                className="flex items-center gap-3 px-3 py-2 rounded-xl hover:bg-muted transition-colors group"
            >
                <div className={`h-8 w-8 rounded-full flex items-center justify-center ring-1 shadow-sm ${isAdmin ? 'bg-primary/10 ring-primary/30 text-primary' : 'bg-emerald-50 ring-emerald-200 text-emerald-600 dark:bg-emerald-900/30 dark:ring-emerald-800 dark:text-emerald-400'}`}>
                    {user?.avatar_url ? (
                        <img src={user.avatar_url} alt="" className="h-8 w-8 rounded-full object-cover" />
                    ) : (
                        <User size={14} />
                    )}
                </div>
                <div className="text-left hidden sm:block">
                    <p className="text-sm font-medium text-foreground">{displayName}</p>
                    <p className="text-[10px] text-muted-foreground">{roleLabel}</p>
                </div>
                <ChevronDown size={16} className={`text-muted-foreground transition-transform ${open ? 'rotate-180' : ''}`} />
            </button>

            {open && (
                <div className="absolute right-0 top-full mt-2 w-56 bg-card border border-border rounded-xl shadow-lg z-50 animate-slide-down overflow-hidden">
                    <div className="p-4 border-b border-border">
                        <div className="flex items-center gap-3">
                            <div className={`h-10 w-10 rounded-full flex items-center justify-center ring-1 ${isAdmin ? 'bg-primary/10 ring-primary/30 text-primary' : 'bg-emerald-50 ring-emerald-200 text-emerald-600 dark:bg-emerald-900/30 dark:ring-emerald-800 dark:text-emerald-400'}`}>
                                {user?.avatar_url ? (
                                    <img src={user.avatar_url} alt="" className="h-10 w-10 rounded-full object-cover" />
                                ) : (
                                    <User size={18} />
                                )}
                            </div>
                            <div className="min-w-0">
                                <p className="text-sm font-semibold text-foreground truncate">{displayName}</p>
                                <p className="text-xs text-muted-foreground truncate">{roleLabel}</p>
                            </div>
                        </div>
                    </div>
                    <div className="py-1">
                        <button
                            onClick={handleProfile}
                            className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-foreground hover:bg-muted transition-colors"
                        >
                            <Settings size={16} className="text-muted-foreground" />
                            个人中心
                        </button>
                        <button
                            onClick={handleToggleTheme}
                            className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-foreground hover:bg-muted transition-colors"
                        >
                            {isDark ? (
                                <Sun size={16} className="text-muted-foreground" />
                            ) : (
                                <Moon size={16} className="text-muted-foreground" />
                            )}
                            {isDark ? '切换亮色' : '切换暗色'}
                        </button>
                    </div>
                    <div className="py-1 border-t border-border">
                        <button
                            onClick={handleLogout}
                            className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-destructive hover:bg-destructive/10 transition-colors"
                        >
                            <LogOut size={16} />
                            退出登录
                        </button>
                    </div>
                </div>
            )}
        </div>
    )
}
