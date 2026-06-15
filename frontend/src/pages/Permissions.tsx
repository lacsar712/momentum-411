import { useEffect, useState, useCallback } from 'react'
import { api } from '../lib/api'
import { useToast } from '../components/Toast'
import { useAuth } from '../lib/auth'
import Modal from '../components/Modal'
import { User, Shield, ChevronDown, ChevronRight, X, Plus, Trash2, Info, Lock } from 'lucide-react'

interface RoleItem {
    id: number
    name: string
    description: string | null
    is_builtin: boolean
    created_at: string
    permissions: { id: number; code: string; name: string; module: string }[]
}

interface UserItem {
    id: number
    username: string
    role: string
    avatar_url: string | null
    created_at: string
    last_login: string | null
    roles: { id: number; name: string; description: string | null }[]
    permissions: string[]
}

interface PermissionGroup {
    module: string
    permissions: {
        id: number
        code: string
        name: string
        description: string | null
        protected_apis: string[]
    }[]
}

export default function Permissions() {
    const { pushToast } = useToast()
    const { hasPermission } = useAuth()
    const canManage = hasPermission('user.manage')

    const [users, setUsers] = useState<UserItem[]>([])
    const [roles, setRoles] = useState<RoleItem[]>([])
    const [permGroups, setPermGroups] = useState<PermissionGroup[]>([])
    const [loading, setLoading] = useState(true)

    const [selectedUser, setSelectedUser] = useState<UserItem | null>(null)
    const [userDrawerOpen, setUserDrawerOpen] = useState(false)
    const [selectedRole, setSelectedRole] = useState<RoleItem | null>(null)
    const [roleDetailOpen, setRoleDetailOpen] = useState(false)

    const [createRoleOpen, setCreateRoleOpen] = useState(false)
    const [newRoleName, setNewRoleName] = useState('')
    const [newRoleDesc, setNewRoleDesc] = useState('')

    const [expandedModules, setExpandedModules] = useState<Set<string>>(new Set())
    const [hoveredPerm, setHoveredPerm] = useState<string | null>(null)

    const fetchData = useCallback(() => {
        if (!canManage) return
        setLoading(true)
        Promise.all([
            api.get('/admin/users'),
            api.get('/admin/roles'),
            api.get('/admin/permissions'),
        ])
            .then(([usersRes, rolesRes, permsRes]) => {
                setUsers(usersRes.data)
                setRoles(rolesRes.data)
                setPermGroups(permsRes.data)
            })
            .catch(() => pushToast('加载权限数据失败', 'error'))
            .finally(() => setLoading(false))
    }, [canManage])

    useEffect(() => {
        fetchData()
    }, [fetchData])

    const toggleModule = (mod: string) => {
        setExpandedModules((prev) => {
            const next = new Set(prev)
            if (next.has(mod)) next.delete(mod)
            else next.add(mod)
            return next
        })
    }

    const handleCreateRole = () => {
        if (!newRoleName.trim()) {
            pushToast('请输入角色名', 'error')
            return
        }
        api.post('/admin/roles', { name: newRoleName, description: newRoleDesc || null })
            .then(() => {
                pushToast('角色创建成功', 'success')
                setCreateRoleOpen(false)
                setNewRoleName('')
                setNewRoleDesc('')
                fetchData()
            })
            .catch((err) => {
                pushToast(err.response?.data?.detail || '创建失败', 'error')
            })
    }

    const handleDeleteRole = (roleId: number) => {
        if (!confirm('确认删除此角色？该操作不可恢复。')) return
        api.delete(`/admin/roles/${roleId}`)
            .then(() => {
                pushToast('角色已删除', 'success')
                if (selectedRole?.id === roleId) {
                    setRoleDetailOpen(false)
                    setSelectedRole(null)
                }
                fetchData()
            })
            .catch((err) => {
                pushToast(err.response?.data?.detail || '删除失败', 'error')
            })
    }

    const handleAssignRole = (userId: number, roleId: number) => {
        api.post(`/admin/users/${userId}/roles`, { role_id: roleId })
            .then(() => {
                pushToast('角色已分配', 'success')
                fetchData()
                refreshSelectedUser(userId)
            })
            .catch((err) => pushToast(err.response?.data?.detail || '分配失败', 'error'))
    }

    const handleRemoveRole = (userId: number, roleId: number) => {
        api.delete(`/admin/users/${userId}/roles/${roleId}`)
            .then(() => {
                pushToast('角色已移除', 'success')
                fetchData()
                refreshSelectedUser(userId)
            })
            .catch((err) => pushToast(err.response?.data?.detail || '移除失败', 'error'))
    }

    const handleTogglePermission = (roleId: number, permId: number, currentlyAssigned: boolean) => {
        if (currentlyAssigned) {
            api.delete(`/admin/roles/${roleId}/permissions/${permId}`)
                .then(() => {
                    pushToast('权限已移除', 'success')
                    fetchData()
                    refreshSelectedRole(roleId)
                })
                .catch((err) => pushToast(err.response?.data?.detail || '移除失败', 'error'))
        } else {
            api.post(`/admin/roles/${roleId}/permissions`, { permission_id: permId })
                .then(() => {
                    pushToast('权限已分配', 'success')
                    fetchData()
                    refreshSelectedRole(roleId)
                })
                .catch((err) => pushToast(err.response?.data?.detail || '分配失败', 'error'))
        }
    }

    const refreshSelectedUser = (userId: number) => {
        api.get(`/admin/users/${userId}`).then((res) => setSelectedUser(res.data)).catch(() => {})
    }

    const refreshSelectedRole = (roleId: number) => {
        api.get(`/admin/roles`).then((res) => {
            const updated = res.data.find((r: RoleItem) => r.id === roleId)
            if (updated) setSelectedRole(updated)
        }).catch(() => {})
    }

    if (!canManage) {
        return (
            <div className="flex items-center justify-center h-96">
                <div className="text-center">
                    <Lock size={48} className="mx-auto text-muted-foreground mb-4" />
                    <h3 className="text-lg font-semibold text-foreground">权限不足</h3>
                    <p className="text-sm text-muted-foreground mt-1">您没有权限访问此页面</p>
                </div>
            </div>
        )
    }

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-2xl font-semibold">权限管理</h2>
                <p className="text-sm text-muted-foreground">用户角色分配、角色权限配置与权限点总览</p>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
                {/* ====== 用户列表 ====== */}
                <div className="rounded-2xl border border-border bg-card shadow-sm">
                    <div className="px-6 py-4 border-b border-border flex items-center gap-2">
                        <User size={18} className="text-primary" />
                        <h3 className="text-base font-semibold">用户列表</h3>
                        <span className="ml-auto text-xs text-muted-foreground">{users.length} 个用户</span>
                    </div>
                    <div className="divide-y divide-border max-h-[600px] overflow-y-auto">
                        {loading ? (
                            <div className="p-8 text-center text-muted-foreground text-sm">加载中...</div>
                        ) : users.length === 0 ? (
                            <div className="p-8 text-center text-muted-foreground text-sm">暂无用户</div>
                        ) : (
                            users.map((u) => (
                                <div
                                    key={u.id}
                                    className="px-6 py-3 hover:bg-muted/50 cursor-pointer transition-colors"
                                    onClick={() => { setSelectedUser(u); setUserDrawerOpen(true) }}
                                >
                                    <div className="flex items-center gap-3">
                                        <div className={`h-8 w-8 rounded-full flex items-center justify-center ring-1 ${u.role === 'admin' ? 'bg-primary/10 ring-primary/30 text-primary' : 'bg-emerald-50 ring-emerald-200 text-emerald-600'}`}>
                                            <User size={14} />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm font-medium text-foreground truncate">{u.username}</p>
                                            <div className="flex items-center gap-1 flex-wrap mt-0.5">
                                                {u.roles.map((r) => (
                                                    <span key={r.id} className="inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium bg-primary/10 text-primary">
                                                        {r.name}
                                                    </span>
                                                ))}
                                                {u.roles.length === 0 && (
                                                    <span className="text-[10px] text-muted-foreground">未分配角色</span>
                                                )}
                                            </div>
                                        </div>
                                        <div className="text-right shrink-0">
                                            <p className="text-[10px] text-muted-foreground">
                                                {u.last_login
                                                    ? new Date(u.last_login).toLocaleDateString('zh-CN')
                                                    : '从未登录'}
                                            </p>
                                            <span className={`inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium ${u.role === 'admin' ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-600'}`}>
                                                {u.role === 'admin' ? '管理员' : '分析师'}
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>

                {/* ====== 角色列表 ====== */}
                <div className="rounded-2xl border border-border bg-card shadow-sm">
                    <div className="px-6 py-4 border-b border-border flex items-center gap-2">
                        <Shield size={18} className="text-primary" />
                        <h3 className="text-base font-semibold">角色列表</h3>
                        <button
                            className="ml-auto flex items-center gap-1 rounded-lg bg-primary px-3 py-1 text-xs text-primary-foreground hover:bg-primary/90"
                            onClick={() => setCreateRoleOpen(true)}
                        >
                            <Plus size={12} />
                            新建
                        </button>
                    </div>
                    <div className="divide-y divide-border max-h-[600px] overflow-y-auto">
                        {loading ? (
                            <div className="p-8 text-center text-muted-foreground text-sm">加载中...</div>
                        ) : roles.length === 0 ? (
                            <div className="p-8 text-center text-muted-foreground text-sm">暂无角色</div>
                        ) : (
                            roles.map((r) => (
                                <div
                                    key={r.id}
                                    className="px-6 py-3 hover:bg-muted/50 cursor-pointer transition-colors"
                                    onClick={() => { setSelectedRole(r); setRoleDetailOpen(true) }}
                                >
                                    <div className="flex items-center gap-3">
                                        <div className={`h-8 w-8 rounded-lg flex items-center justify-center ${r.is_builtin ? 'bg-amber-50 text-amber-600' : 'bg-slate-100 text-slate-500'}`}>
                                            <Shield size={14} />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2">
                                                <p className="text-sm font-medium text-foreground truncate">{r.name}</p>
                                                {r.is_builtin && (
                                                    <Lock size={10} className="text-amber-500" />
                                                )}
                                            </div>
                                            <p className="text-xs text-muted-foreground truncate">{r.description || '无描述'}</p>
                                        </div>
                                        <div className="text-right shrink-0">
                                            <span className="text-xs text-muted-foreground">{r.permissions.length} 个权限</span>
                                        </div>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>

                {/* ====== 权限点视图 ====== */}
                <div className="rounded-2xl border border-border bg-card shadow-sm">
                    <div className="px-6 py-4 border-b border-border flex items-center gap-2">
                        <Info size={18} className="text-primary" />
                        <h3 className="text-base font-semibold">权限点总览</h3>
                        <span className="ml-auto text-xs text-muted-foreground">只读 · 按模块分组</span>
                    </div>
                    <div className="max-h-[600px] overflow-y-auto">
                        {loading ? (
                            <div className="p-8 text-center text-muted-foreground text-sm">加载中...</div>
                        ) : (
                            permGroups.map((g) => (
                                <div key={g.module} className="border-b border-border last:border-b-0">
                                    <button
                                        className="w-full px-6 py-3 flex items-center gap-2 hover:bg-muted/50 transition-colors"
                                        onClick={() => toggleModule(g.module)}
                                    >
                                        {expandedModules.has(g.module) ? (
                                            <ChevronDown size={14} className="text-muted-foreground" />
                                        ) : (
                                            <ChevronRight size={14} className="text-muted-foreground" />
                                        )}
                                        <span className="text-sm font-medium text-foreground">{g.module}</span>
                                        <span className="text-xs text-muted-foreground ml-1">({g.permissions.length})</span>
                                    </button>
                                    {expandedModules.has(g.module) && (
                                        <div className="px-6 pb-3 space-y-1">
                                            {g.permissions.map((p) => (
                                                <div
                                                    key={p.code}
                                                    className="relative px-3 py-2 rounded-lg bg-muted/50 group"
                                                    onMouseEnter={() => setHoveredPerm(p.code)}
                                                    onMouseLeave={() => setHoveredPerm(null)}
                                                >
                                                    <div className="flex items-center gap-2">
                                                        <code className="text-xs font-mono text-primary">{p.code}</code>
                                                        <span className="text-xs text-foreground">{p.name}</span>
                                                    </div>
                                                    {p.description && (
                                                        <p className="text-[10px] text-muted-foreground mt-0.5">{p.description}</p>
                                                    )}
                                                    {hoveredPerm === p.code && p.protected_apis.length > 0 && (
                                                        <div className="absolute left-0 right-0 top-full mt-1 z-50 bg-popover border border-border rounded-lg shadow-lg p-3 text-xs">
                                                            <p className="font-medium text-foreground mb-1">保护的接口：</p>
                                                            <div className="space-y-0.5">
                                                                {p.protected_apis.map((api_str, i) => (
                                                                    <code key={i} className="block text-muted-foreground font-mono text-[10px]">{api_str}</code>
                                                                ))}
                                                            </div>
                                                        </div>
                                                    )}
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            ))
                        )}
                    </div>
                </div>
            </div>

            {/* ====== 用户角色分配抽屉 ====== */}
            {userDrawerOpen && selectedUser && (
                <div className="fixed inset-0 z-50 flex justify-end">
                    <div className="absolute inset-0 bg-black/30" onClick={() => setUserDrawerOpen(false)} />
                    <div className="relative w-full max-w-md bg-card shadow-xl flex flex-col animate-slide-in-right">
                        <div className="px-6 py-4 border-b border-border flex items-center justify-between">
                            <div>
                                <h3 className="text-base font-semibold">{selectedUser.username}</h3>
                                <p className="text-xs text-muted-foreground">分配角色</p>
                            </div>
                            <button onClick={() => setUserDrawerOpen(false)} className="h-8 w-8 flex items-center justify-center rounded-lg hover:bg-muted">
                                <X size={16} className="text-muted-foreground" />
                            </button>
                        </div>
                        <div className="flex-1 overflow-y-auto p-6 space-y-4">
                            <div>
                                <p className="text-xs text-muted-foreground mb-2">当前角色</p>
                                <div className="space-y-2">
                                    {selectedUser.roles.length === 0 && (
                                        <p className="text-sm text-muted-foreground">暂无角色</p>
                                    )}
                                    {selectedUser.roles.map((r) => (
                                        <div key={r.id} className="flex items-center justify-between px-3 py-2 rounded-lg bg-primary/5 border border-primary/10">
                                            <div>
                                                <p className="text-sm font-medium text-foreground">{r.name}</p>
                                                {r.description && <p className="text-[10px] text-muted-foreground">{r.description}</p>}
                                            </div>
                                            <button
                                                onClick={() => handleRemoveRole(selectedUser.id, r.id)}
                                                className="h-6 w-6 flex items-center justify-center rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                                            >
                                                <X size={12} />
                                            </button>
                                        </div>
                                    ))}
                                </div>
                            </div>
                            <div>
                                <p className="text-xs text-muted-foreground mb-2">添加角色</p>
                                <div className="space-y-2">
                                    {roles
                                        .filter((r) => !selectedUser.roles.some((ur) => ur.id === r.id))
                                        .map((r) => (
                                            <button
                                                key={r.id}
                                                onClick={() => handleAssignRole(selectedUser.id, r.id)}
                                                className="w-full flex items-center gap-2 px-3 py-2 rounded-lg border border-border hover:bg-muted transition-colors text-left"
                                            >
                                                <Plus size={12} className="text-muted-foreground" />
                                                <div>
                                                    <p className="text-sm text-foreground">{r.name}</p>
                                                    {r.description && <p className="text-[10px] text-muted-foreground">{r.description}</p>}
                                                </div>
                                            </button>
                                        ))}
                                    {roles.filter((r) => !selectedUser.roles.some((ur) => ur.id === r.id)).length === 0 && (
                                        <p className="text-sm text-muted-foreground">所有角色已分配</p>
                                    )}
                                </div>
                            </div>
                            {selectedUser.permissions.length > 0 && (
                                <div>
                                    <p className="text-xs text-muted-foreground mb-2">已生效权限点 ({selectedUser.permissions.length})</p>
                                    <div className="flex flex-wrap gap-1">
                                        {selectedUser.permissions.map((p) => (
                                            <span key={p} className="inline-flex px-1.5 py-0.5 rounded text-[10px] font-mono bg-muted text-muted-foreground">{p}</span>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* ====== 角色详情弹窗 ====== */}
            <Modal
                open={roleDetailOpen}
                title={selectedRole?.name || '角色详情'}
                onClose={() => { setRoleDetailOpen(false); setSelectedRole(null) }}
                maxWidth="max-w-2xl"
                footer={
                    selectedRole && !selectedRole.is_builtin ? (
                        <div className="flex justify-between">
                            <button
                                className="rounded-lg border border-destructive/20 text-destructive px-3 py-1.5 text-xs hover:bg-destructive/10 flex items-center gap-1"
                                onClick={() => { handleDeleteRole(selectedRole.id); setRoleDetailOpen(false) }}
                            >
                                <Trash2 size={12} />
                                删除角色
                            </button>
                            <button className="rounded-lg border border-border px-4 py-2 text-sm" onClick={() => setRoleDetailOpen(false)}>关闭</button>
                        </div>
                    ) : (
                        <button className="rounded-lg border border-border px-4 py-2 text-sm" onClick={() => setRoleDetailOpen(false)}>关闭</button>
                    )
                }
            >
                {selectedRole && (
                    <div className="space-y-4">
                        {selectedRole.is_builtin && (
                            <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-50 border border-amber-200 text-amber-700 text-xs">
                                <Lock size={12} />
                                这是系统内置角色，不可修改或删除
                            </div>
                        )}
                        {selectedRole.description && (
                            <p className="text-sm text-muted-foreground">{selectedRole.description}</p>
                        )}
                        <div>
                            <p className="text-xs text-muted-foreground mb-2">权限配置</p>
                            <div className="space-y-3">
                                {permGroups.map((g) => (
                                    <div key={g.module}>
                                        <p className="text-xs font-semibold text-foreground mb-1">{g.module}</p>
                                        <div className="grid grid-cols-2 gap-1">
                                            {g.permissions.map((p) => {
                                                const assigned = selectedRole.permissions.some((rp) => rp.id === p.id)
                                                return (
                                                    <label
                                                        key={p.id}
                                                        className={`flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs cursor-pointer transition-colors ${assigned ? 'bg-primary/5 border border-primary/20' : 'hover:bg-muted border border-transparent'} ${selectedRole.is_builtin ? 'pointer-events-none' : ''}`}
                                                    >
                                                        <input
                                                            type="checkbox"
                                                            checked={assigned}
                                                            onChange={() => handleTogglePermission(selectedRole.id, p.id, assigned)}
                                                            disabled={selectedRole.is_builtin}
                                                            className="rounded border-border text-primary focus:ring-primary"
                                                        />
                                                        <div>
                                                            <span className="font-medium text-foreground">{p.name}</span>
                                                            <code className="ml-1 text-[10px] text-muted-foreground">{p.code}</code>
                                                        </div>
                                                    </label>
                                                )
                                            })}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                )}
            </Modal>

            {/* ====== 新建角色弹窗 ====== */}
            <Modal
                open={createRoleOpen}
                title="新建角色"
                onClose={() => setCreateRoleOpen(false)}
                footer={(
                    <div className="flex justify-end gap-3">
                        <button className="rounded-lg border border-border px-4 py-2 text-sm" onClick={() => setCreateRoleOpen(false)}>取消</button>
                        <button className="rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground" onClick={handleCreateRole}>创建</button>
                    </div>
                )}
            >
                <div className="space-y-4">
                    <div>
                        <label className="text-xs text-muted-foreground">角色名称</label>
                        <input
                            className="mt-2 w-full rounded-lg border border-border px-3 py-2 text-sm bg-background"
                            value={newRoleName}
                            onChange={(e) => setNewRoleName(e.target.value)}
                            placeholder="例如：数据分析师"
                        />
                    </div>
                    <div>
                        <label className="text-xs text-muted-foreground">角色描述</label>
                        <textarea
                            className="mt-2 w-full rounded-lg border border-border px-3 py-2 text-sm bg-background resize-none"
                            rows={3}
                            value={newRoleDesc}
                            onChange={(e) => setNewRoleDesc(e.target.value)}
                            placeholder="描述此角色的职责和权限范围"
                        />
                    </div>
                </div>
            </Modal>
        </div>
    )
}
