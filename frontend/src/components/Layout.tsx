import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import UserMenu from './UserMenu'
import NotificationBell from './NotificationBell'

export default function Layout() {
    return (
        <div className="flex h-screen w-full relative overflow-hidden bg-background">
            <Sidebar />

            <div className="flex-1 flex flex-col pl-64 relative z-10">
                <header className="h-16 flex items-center justify-between px-8 border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-40 shrink-0">
                    <div></div>
                    <div className="flex items-center gap-2">
                        <NotificationBell />
                        <UserMenu />
                    </div>
                </header>

                <main className="flex-1 overflow-y-auto scrollbar-none">
                    <div className="min-h-full max-w-7xl mx-auto p-8 animate-fade-in-up">
                        <Outlet />
                    </div>
                </main>
            </div>
        </div>
    )
}
