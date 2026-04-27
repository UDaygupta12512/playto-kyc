import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { reviewerAPI } from '../api'
import { StateBadge, Spinner } from '../components/ui'
import { toast } from '../components/Toast'

const FILTER_TABS = [
  { key: 'active',              label: 'Active Queue',     icon: '⏳' },
  { key: 'submitted',           label: 'Submitted',        icon: '📤' },
  { key: 'under_review',        label: 'Under Review',     icon: '🔍' },
  { key: 'more_info_requested', label: 'More Info',        icon: '📋' },
  { key: 'approved',            label: 'Approved',         icon: '✓'  },
  { key: 'rejected',            label: 'Rejected',         icon: '✕'  },
  { key: 'all',                 label: 'All',              icon: '☰'  },
]

export function ReviewerDashboard() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const [metrics, setMetrics] = useState(null)
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [activeTab, setActiveTab] = useState('active')
  const [search, setSearch] = useState('')
  const intervalRef = useRef()

  const fetchData = useCallback(async (tab, silent = false) => {
    if (!silent) setRefreshing(true)
    try {
      const [qRes, mRes] = await Promise.all([
        reviewerAPI.getQueue(tab),
        reviewerAPI.getMetrics(),
      ])
      setRows(qRes.data.results || qRes.data)
      setMetrics(mRes.data)
    } catch (err) {
      if (!silent) toast.error(err.message)
    } finally {
      setRefreshing(false)
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    setLoading(true)
    fetchData(activeTab)
    // Auto-refresh every 30s (silent)
    intervalRef.current = setInterval(() => fetchData(activeTab, true), 30_000)
    return () => clearInterval(intervalRef.current)
  }, [activeTab, fetchData])

  const handleRefresh = () => fetchData(activeTab)

  const handleTabChange = (key) => {
    setActiveTab(key)
    setSearch('')
  }

  // Client-side search filter
  const filtered = rows.filter(s => {
    if (!search) return true
    const q = search.toLowerCase()
    return (
      s.merchant?.username?.toLowerCase().includes(q) ||
      s.full_name?.toLowerCase().includes(q) ||
      s.business_name?.toLowerCase().includes(q) ||
      String(s.id).includes(q)
    )
  })

  const stateCounts = metrics?.state_counts || {}

  return (
    <div className="min-h-screen bg-surface-50">
      <header className="bg-white border-b border-gray-100 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 bg-brand-500 rounded-lg flex items-center justify-center">
            <span className="text-white text-sm font-bold">P</span>
          </div>
          <span className="font-semibold text-gray-900">Playto Pay</span>
          <span className="text-gray-200 mx-1">|</span>
          <span className="text-sm text-gray-400">Reviewer Dashboard</span>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={handleRefresh} disabled={refreshing}
            className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1 disabled:opacity-40">
            {refreshing ? <Spinner /> : '↻'} Refresh
          </button>
          <span className="text-sm text-gray-500">{user?.username}</span>
          <button onClick={logout} className="text-sm text-gray-400 hover:text-gray-600">Sign out</button>
        </div>
      </header>

      <main className="max-w-6xl mx-auto py-6 px-4">
        {/* Metric cards */}
        {metrics && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
            <MetricCard label="In Queue"      value={metrics.total_in_queue}    sub="active submissions"       accent="text-blue-600"   dot="bg-blue-500" />
            <MetricCard label="SLA at Risk"   value={metrics.at_risk_count}     sub="> 24h in queue"           accent={metrics.at_risk_count > 0 ? 'text-orange-600' : 'text-gray-400'} dot={metrics.at_risk_count > 0 ? 'bg-orange-500' : 'bg-gray-300'} />
            <MetricCard label="Avg Queue Age" value={metrics.avg_queue_age_hours != null ? `${metrics.avg_queue_age_hours}h` : '—'} sub="since submission" accent="text-purple-600" dot="bg-purple-500" />
            <MetricCard label="Approval (7d)" value={metrics.approval_rate_7d != null ? `${metrics.approval_rate_7d}%` : '—'} sub={`${metrics.total_approved_7d}/${metrics.total_resolved_7d} resolved`} accent="text-green-600" dot="bg-green-500" />
          </div>
        )}

        {/* Filter tabs */}
        <div className="flex gap-1 mb-4 overflow-x-auto pb-1">
          {FILTER_TABS.map(({ key, label, icon }) => {
            const count = key === 'active'
              ? stateCounts.active
              : key === 'all'
              ? Object.values(stateCounts).reduce((a, b) => a + b, 0) - (stateCounts.active || 0)
              : stateCounts[key]
            return (
              <button key={key}
                onClick={() => handleTabChange(key)}
                className={`flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors
                  ${activeTab === key
                    ? 'bg-brand-500 text-white shadow-sm'
                    : 'bg-white text-gray-500 border border-gray-100 hover:border-gray-200 hover:text-gray-700'}`}>
                <span>{icon}</span>
                <span>{label}</span>
                {count != null && count > 0 && (
                  <span className={`text-xs rounded-full px-1.5 py-0.5 font-medium
                    ${activeTab === key ? 'bg-white/20 text-white' : 'bg-gray-100 text-gray-500'}`}>
                    {count}
                  </span>
                )}
              </button>
            )
          })}
        </div>

        {/* Search */}
        <div className="mb-4 relative">
          <span className="absolute left-3 top-2.5 text-gray-300 text-sm">🔍</span>
          <input
            className="input pl-8 text-sm"
            placeholder="Search by name, business, username, or #ID…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          {search && (
            <button className="absolute right-3 top-2.5 text-gray-300 hover:text-gray-500 text-sm"
              onClick={() => setSearch('')}>✕</button>
          )}
        </div>

        {/* Table */}
        {loading ? (
          <div className="flex justify-center py-20"><Spinner size="lg" /></div>
        ) : (
          <div className="card overflow-hidden">
            {filtered.length === 0 ? (
              <div className="text-center py-16">
                <p className="text-3xl mb-2">{search ? '🔍' : '✓'}</p>
                <p className="text-sm text-gray-400 font-medium">
                  {search ? `No results for "${search}"` : 'Nothing here'}
                </p>
                {search && (
                  <button onClick={() => setSearch('')} className="mt-2 text-xs text-brand-500 hover:underline">
                    Clear search
                  </button>
                )}
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 bg-surface-50 text-left">
                    <th className="text-xs font-semibold text-gray-400 px-4 py-3">#</th>
                    <th className="text-xs font-semibold text-gray-400 px-4 py-3">Merchant</th>
                    <th className="text-xs font-semibold text-gray-400 px-4 py-3">Business</th>
                    <th className="text-xs font-semibold text-gray-400 px-4 py-3">Status</th>
                    <th className="text-xs font-semibold text-gray-400 px-4 py-3">Docs</th>
                    <th className="text-xs font-semibold text-gray-400 px-4 py-3">Queue Age</th>
                    <th className="text-xs font-semibold text-gray-400 px-4 py-3">Submitted</th>
                    <th className="px-4 py-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(sub => (
                    <tr key={sub.id}
                      onClick={() => navigate(`/reviewer/submission/${sub.id}`)}
                      className="border-b border-gray-50 last:border-0 hover:bg-surface-50 cursor-pointer transition-colors group">
                      <td className="px-4 py-3 font-mono text-gray-400 text-xs">#{sub.id}</td>
                      <td className="px-4 py-3">
                        <p className="font-medium text-gray-800">{sub.merchant?.username}</p>
                        <p className="text-xs text-gray-400">{sub.full_name || '—'}</p>
                      </td>
                      <td className="px-4 py-3">
                        <p className="text-gray-700 font-medium">{sub.business_name || <span className="text-gray-300">—</span>}</p>
                        {sub.monthly_volume_usd && (
                          <p className="text-xs text-gray-400">${Number(sub.monthly_volume_usd).toLocaleString()}/mo</p>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <StateBadge state={sub.state} atRisk={sub.is_at_risk} />
                      </td>
                      <td className="px-4 py-3">
                        <DocCount docs={sub.documents} />
                      </td>
                      <td className="px-4 py-3">
                        {sub.queue_age_hours != null ? (
                          <span className={`text-xs font-mono font-semibold ${sub.is_at_risk ? 'text-orange-500' : 'text-gray-500'}`}>
                            {sub.queue_age_hours}h {sub.is_at_risk && '⚠'}
                          </span>
                        ) : <span className="text-gray-300 text-xs">—</span>}
                      </td>
                      <td className="px-4 py-3 text-gray-400 text-xs">
                        {sub.submitted_at ? new Date(sub.submitted_at).toLocaleDateString('en-IN') : '—'}
                      </td>
                      <td className="px-4 py-3 text-brand-500 text-xs font-semibold opacity-0 group-hover:opacity-100 transition-opacity">
                        Review →
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        <p className="text-xs text-gray-300 text-center mt-3">
          Auto-refreshes every 30s · Last updated: {new Date().toLocaleTimeString('en-IN')}
        </p>
      </main>
    </div>
  )
}

function MetricCard({ label, value, sub, accent, dot }) {
  return (
    <div className="card p-4">
      <div className="flex items-center gap-1.5 mb-2">
        <div className={`w-2 h-2 rounded-full ${dot}`} />
        <p className="text-xs text-gray-400 font-medium uppercase tracking-wide">{label}</p>
      </div>
      <p className={`text-2xl font-bold ${accent}`}>{value}</p>
      <p className="text-xs text-gray-400 mt-0.5">{sub}</p>
    </div>
  )
}

function DocCount({ docs = [] }) {
  const total = 3
  const uploaded = docs.length
  return (
    <div className="flex items-center gap-0.5">
      {[...Array(total)].map((_, i) => (
        <div key={i} className={`w-2 h-2 rounded-sm ${i < uploaded ? 'bg-green-400' : 'bg-gray-200'}`} />
      ))}
      <span className="text-xs text-gray-400 ml-1">{uploaded}/{total}</span>
    </div>
  )
}
