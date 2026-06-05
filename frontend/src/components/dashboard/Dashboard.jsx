import { useEffect, useState } from 'react'
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import { Activity, Clock, Zap, AlertCircle, TrendingUp, Database } from 'lucide-react'
import { api } from '../../lib/api'
import { format } from 'date-fns'

const COLORS = ['#7c6af7', '#10b981', '#f59e0b', '#ef4444', '#06b6d4']

function StatCard({ icon: Icon, label, value, sub, color = 'text-ollive-accent' }) {
  return (
    <div className="bg-ollive-surface border border-ollive-border rounded-xl p-4">
      <div className="flex items-center gap-2 mb-3">
        <Icon size={14} className={color} />
        <span className="text-xs text-ollive-muted font-mono uppercase tracking-wider">{label}</span>
      </div>
      <div className="text-2xl font-mono font-medium text-ollive-text">{value}</div>
      {sub && <div className="text-xs text-ollive-muted mt-1">{sub}</div>}
    </div>
  )
}

export default function Dashboard() {
  const [overview, setOverview] = useState(null)
  const [byProvider, setByProvider] = useState([])
  const [histogram, setHistogram] = useState([])
  const [timeseries, setTimeseries] = useState([])
  const [recentLogs, setRecentLogs] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetch = async () => {
      try {
        const [ov, bp, hist, ts, logs] = await Promise.all([
          api.get('/metrics/overview'),
          api.get('/metrics/by-provider'),
          api.get('/metrics/latency-histogram'),
          api.get('/metrics/timeseries'),
          api.get('/metrics/recent-logs?limit=20'),
        ])
        setOverview(ov)
        setByProvider(bp.providers || [])
        setHistogram(hist.buckets || [])
        setTimeseries(ts.timeseries || [])
        setRecentLogs(logs.logs || [])
      } catch (e) {
        console.error(e)
      } finally {
        setLoading(false)
      }
    }
    fetch()
    const iv = setInterval(fetch, 30000)
    return () => clearInterval(iv)
  }, [])

  if (loading) return (
    <div className="flex-1 flex items-center justify-center">
      <div className="text-ollive-muted text-xs font-mono animate-pulse">Loading metrics...</div>
    </div>
  )

  const tsData = timeseries.map(t => ({
    time: t.hour ? format(new Date(t.hour), 'HH:mm') : '',
    requests: t.request_count,
    latency: Math.round(t.avg_latency_ms),
  }))

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      <div className="flex items-center gap-2 mb-2">
        <Activity size={16} className="text-ollive-accent" />
        <h1 className="font-mono text-sm text-ollive-text font-medium tracking-wider">Observability Dashboard</h1>
        <span className="ml-auto text-[10px] font-mono text-ollive-muted">Last 24h · Auto-refresh 30s</span>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard icon={Zap} label="Total Requests" value={overview?.total_requests?.toLocaleString() || '0'} />
        <StatCard icon={Clock} label="Avg Latency" value={`${overview?.avg_latency_ms || 0}ms`} sub={`P0: ${overview?.min_latency_ms || 0}ms · Pmax: ${overview?.max_latency_ms || 0}ms`} />
        <StatCard icon={AlertCircle} label="Error Rate" value={`${overview?.error_rate || 0}%`} sub={`${overview?.error_count || 0} errors`} color="text-red-400" />
        <StatCard icon={Database} label="Total Tokens" value={(overview?.total_tokens || 0).toLocaleString()} sub={`Avg TTFT: ${overview?.avg_ttft_ms || 0}ms`} color="text-emerald-400" />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Timeseries */}
        <div className="bg-ollive-surface border border-ollive-border rounded-xl p-4">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp size={13} className="text-ollive-accent" />
            <span className="text-xs font-mono text-ollive-muted uppercase tracking-wider">Requests over time</span>
          </div>
          {tsData.length > 0 ? (
            <ResponsiveContainer width="100%" height={160}>
              <AreaChart data={tsData}>
                <defs>
                  <linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#7c6af7" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#7c6af7" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#6b7280' }} />
                <YAxis tick={{ fontSize: 10, fill: '#6b7280' }} />
                <Tooltip
                  contentStyle={{ background: '#111118', border: '1px solid #1e1e2e', borderRadius: 8, fontSize: 11 }}
                  labelStyle={{ color: '#e2e8f0' }}
                />
                <Area type="monotone" dataKey="requests" stroke="#7c6af7" fill="url(#g1)" strokeWidth={1.5} />
              </AreaChart>
            </ResponsiveContainer>
          ) : <div className="h-40 flex items-center justify-center text-xs text-ollive-muted">No data yet</div>}
        </div>

        {/* Latency histogram */}
        <div className="bg-ollive-surface border border-ollive-border rounded-xl p-4">
          <div className="flex items-center gap-2 mb-4">
            <Clock size={13} className="text-ollive-accent" />
            <span className="text-xs font-mono text-ollive-muted uppercase tracking-wider">Latency distribution</span>
          </div>
          {histogram.some(h => h.count > 0) ? (
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={histogram}>
                <XAxis dataKey="label" tick={{ fontSize: 9, fill: '#6b7280' }} />
                <YAxis tick={{ fontSize: 10, fill: '#6b7280' }} />
                <Tooltip
                  contentStyle={{ background: '#111118', border: '1px solid #1e1e2e', borderRadius: 8, fontSize: 11 }}
                  labelStyle={{ color: '#e2e8f0' }}
                />
                <Bar dataKey="count" fill="#7c6af7" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <div className="h-40 flex items-center justify-center text-xs text-ollive-muted">No data yet</div>}
        </div>
      </div>

      {/* Provider breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-ollive-surface border border-ollive-border rounded-xl p-4">
          <div className="text-xs font-mono text-ollive-muted uppercase tracking-wider mb-3">Provider breakdown</div>
          {byProvider.length === 0 ? (
            <div className="text-xs text-ollive-muted py-4 text-center">No data yet</div>
          ) : (
            <table className="w-full text-xs">
              <thead>
                <tr className="text-ollive-muted font-mono text-[10px] uppercase tracking-wider border-b border-ollive-border">
                  <th className="text-left pb-2">Provider</th>
                  <th className="text-left pb-2">Model</th>
                  <th className="text-right pb-2">Requests</th>
                  <th className="text-right pb-2">Avg Latency</th>
                  <th className="text-right pb-2">Tokens</th>
                </tr>
              </thead>
              <tbody>
                {byProvider.map((p, i) => (
                  <tr key={i} className="border-b border-ollive-border/40 hover:bg-white/[0.01]">
                    <td className="py-2 text-ollive-text font-mono capitalize">{p.provider}</td>
                    <td className="py-2 text-ollive-muted font-mono text-[10px]">{p.model}</td>
                    <td className="py-2 text-right text-ollive-text">{p.request_count}</td>
                    <td className="py-2 text-right text-ollive-text">{p.avg_latency_ms}ms</td>
                    <td className="py-2 text-right text-ollive-muted">{(p.total_tokens || 0).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Pie - providers */}
        <div className="bg-ollive-surface border border-ollive-border rounded-xl p-4">
          <div className="text-xs font-mono text-ollive-muted uppercase tracking-wider mb-3">Share by provider</div>
          {byProvider.length > 0 ? (
            <ResponsiveContainer width="100%" height={160}>
              <PieChart>
                <Pie data={byProvider} dataKey="request_count" nameKey="provider" cx="50%" cy="50%" outerRadius={60} strokeWidth={0}>
                  {byProvider.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip
                  contentStyle={{ background: '#111118', border: '1px solid #1e1e2e', borderRadius: 8, fontSize: 11 }}
                  formatter={(v, n) => [v + ' requests', n]}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : <div className="h-40 flex items-center justify-center text-xs text-ollive-muted">No data yet</div>}
        </div>
      </div>

      {/* Recent logs */}
      <div className="bg-ollive-surface border border-ollive-border rounded-xl p-4">
        <div className="text-xs font-mono text-ollive-muted uppercase tracking-wider mb-3">Recent inference logs</div>
        <div className="space-y-1">
          {recentLogs.length === 0 && <div className="text-xs text-ollive-muted py-2 text-center">No logs yet</div>}
          {recentLogs.map((log, i) => (
            <div key={i} className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/[0.02] transition-colors text-xs">
              <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${log.status === 'success' ? 'bg-emerald-400' : 'bg-red-400'}`} />
              <span className="font-mono text-ollive-muted w-16 truncate capitalize">{log.provider}</span>
              <span className="font-mono text-[10px] text-ollive-border w-28 truncate">{log.model}</span>
              <span className="text-ollive-text-dim flex-1 truncate">{log.input_preview || '—'}</span>
              <span className="font-mono text-ollive-accent shrink-0">{log.latency_ms ? `${Math.round(log.latency_ms)}ms` : '—'}</span>
              <span className="font-mono text-ollive-muted text-[10px] shrink-0">{log.total_tokens || 0}t</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
