import { useEffect, useState } from 'react'
import { Navigate, Outlet, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import DataCenter from './pages/DataCenter'
import Screening from './pages/Screening'
import Patterns from './pages/Patterns'
import Strategies from './pages/Strategies'
import Backtest from './pages/Backtest'
import Visual from './pages/Visual'
import Concept from './pages/Concept'
import ConceptDetail from './pages/ConceptDetail'
import Index from './pages/Index'
import IndexDetail from './pages/IndexDetail'
import IndexCompare from './pages/IndexCompare'
import Settings from './pages/Settings'
import SystemLogs from './pages/SystemLogs'
import Profile from './pages/Profile'
import Permissions from './pages/Permissions'
import Notifications from './pages/Notifications'
import NotificationPreferences from './pages/NotificationPreferences'
import PortfolioMgmt from './pages/PortfolioMgmt'
import Risk from './pages/Risk'
import Recommend from './pages/Recommend'
import Login from './pages/Login'

function App() {
    const [token, setToken] = useState(() => localStorage.getItem('momentum_token'))

    useEffect(() => {
        const syncToken = () => {
            setToken(localStorage.getItem('momentum_token'))
        }

        // Listen for standard storage events (cross-tab)
        window.addEventListener('storage', syncToken)
        // Listen for custom auth events (same-tab)
        window.addEventListener('momentum-auth', syncToken)

        return () => {
            window.removeEventListener('storage', syncToken)
            window.removeEventListener('momentum-auth', syncToken)
        }
    }, [])

    return (
        <Routes>
            <Route path="/login" element={<Login />} />
            <Route element={token ? <Outlet /> : <Navigate to="/login" replace />}>
                <Route element={<Layout />}>
                    <Route path="/" element={<Dashboard />} />
                    <Route path="/data" element={<DataCenter />} />
                    <Route path="/screening" element={<Screening />} />
                    <Route path="/patterns" element={<Patterns />} />
                    <Route path="/strategies" element={<Strategies />} />
                    <Route path="/backtest" element={<Backtest />} />
                    <Route path="/visual" element={<Visual />} />
                    <Route path="/concept" element={<Concept />} />
                    <Route path="/concept/:code" element={<ConceptDetail />} />
                    <Route path="/index" element={<Index />} />
                    <Route path="/index/:code" element={<IndexDetail />} />
                    <Route path="/index-compare" element={<IndexCompare />} />
                    <Route path="/settings" element={<Settings />} />
                    <Route path="/logs" element={<SystemLogs />} />
                    <Route path="/admin/permissions" element={<Permissions />} />
                    <Route path="/profile" element={<Profile />} />
                    <Route path="/notifications" element={<Notifications />} />
                    <Route path="/notifications/preferences" element={<NotificationPreferences />} />
                    <Route path="/portfolio_mgmt" element={<PortfolioMgmt />} />
                    <Route path="/risk" element={<Risk />} />
                    <Route path="/recommend" element={<Recommend />} />
                </Route>
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
    )
}

export default App
