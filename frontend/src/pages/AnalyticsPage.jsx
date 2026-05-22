import { useState, useEffect } from 'react'
import { getAnalyticsSummary } from '@/services/api'
import { SectionHeader, KPICard, Card, Spinner } from '@/components/ui/index'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, LineChart, Line, CartesianGrid,
} from 'recharts'
import { PageContainer } from '@/components/layout/PageLayout'

// ── Chart design tokens ───────────────────────────────────────────────────────

const CHART_PALETTE = [
  '#8B5CF6', // violet   — primary brand
  '#6366F1', // indigo
  '#3B82F6', // blue
  '#34D399', // emerald
  '#FBBF24', // amber
  '#F87171', // rose-soft
  '#A78BFA', // violet-light
  '#60A5FA', // blue-light
]

// Semantic: keyed by backend risk level name
const RISK_COLORS = {
  Low:      '#34D399', // emerald
  Medium:   '#6366F1', // indigo
  High:     '#F59E0B', // amber
  Critical: '#F43F5E', // rose
}

const TOOLTIP_STYLE = {
  contentStyle: {
    background: 'var(--bg-card)',
    border: '1px solid rgba(139,92,246,0.18)',
    borderRadius: 8,
    fontSize: 12,
    boxShadow: '0 8px 32px rgba(0,0,0,0.35)',
  },
  labelStyle: { color: 'var(--text-primary)', fontWeight: 500, marginBottom: 2 },
  itemStyle:  { color: 'var(--text-secondary)' },
  cursor:     { fill: 'rgba(139,92,246,0.06)' },
}

const LEGEND_STYLE = {
  wrapperStyle: { fontSize: 11, paddingTop: 8, color: 'var(--text-muted)' },
}

const TICK = { fill: 'var(--text-muted)', fontSize: 11 }
const AXIS_LINE = { axisLine: false, tickLine: false }


export default function AnalyticsPage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getAnalyticsSummary().then(setData).finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="flex justify-center items-center min-h-64">
      <Spinner size={36} />
    </div>
  )

  if (!data) return null

  const catData  = Object.entries(data.categories  || {}).map(([name, value]) => ({ name: name.slice(0, 14), value }))
  const riskData = Object.entries(data.risk_levels  || {}).map(([name, value]) => ({ name, value }))
  const langData = Object.entries(data.languages    || {}).map(([name, value]) => ({ name, value }))
  const cityData = Object.entries(data.cities       || {}).map(([name, value]) => ({ name, value }))
  const appStats = data.application_stats || {}

  return (
    <PageContainer size="full">
      <SectionHeader
        eyebrow="Platform Analytics"
        title="Usage Analytics"
        description="Aggregate usage data and platform insights."
      />

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <KPICard label="Total Queries"   value={data.total_queries?.toLocaleString() || 0} icon="🔍" />
        <KPICard label="Applications"    value={appStats.total || 0}                         icon="📋" />
        <KPICard label="Resolved Cases"  value={appStats.by_status?.resolved || 0}            icon="✅" subColor="var(--success-text)" />
        <KPICard label="Languages"       value={Object.keys(data.languages || {}).length}     icon="🌐" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-5">

        {/* Queries by Legal Category — horizontal gradient bars */}
        <Card padding="p-5" className="card-important">
          <div className="label mb-4">Queries by Legal Category</div>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={catData} layout="vertical">
              <defs>
                <linearGradient id="catBarGrad" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%"   stopColor="#6366F1" stopOpacity={0.85} />
                  <stop offset="100%" stopColor="#8B5CF6" stopOpacity={1}    />
                </linearGradient>
              </defs>
              <XAxis type="number"   tick={TICK} {...AXIS_LINE} />
              <YAxis dataKey="name" type="category" tick={TICK} width={100} {...AXIS_LINE} />
              <Tooltip {...TOOLTIP_STYLE} />
              <Bar dataKey="value" fill="url(#catBarGrad)" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        {/* Risk Level Distribution — semantic pie */}
        <Card padding="p-5" className="card-important">
          <div className="label mb-4">Risk Level Distribution</div>
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie
                data={riskData}
                dataKey="value"
                nameKey="name"
                cx="50%" cy="50%"
                outerRadius={85}
                innerRadius={32}
                paddingAngle={3}
                label={({ name, percent }) => percent > 0.05 ? `${(percent * 100).toFixed(0)}%` : ''}
                labelLine={false}
              >
                {riskData.map((entry, i) => (
                  <Cell
                    key={i}
                    fill={RISK_COLORS[entry.name] || CHART_PALETTE[i % CHART_PALETTE.length]}
                    strokeWidth={0}
                  />
                ))}
              </Pie>
              <Legend {...LEGEND_STYLE} />
              <Tooltip {...TOOLTIP_STYLE} />
            </PieChart>
          </ResponsiveContainer>
        </Card>

        {/* Language Usage — violet gradient bars */}
        <Card padding="p-5" className="card-important">
          <div className="label mb-4">Language Usage</div>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={langData}>
              <defs>
                <linearGradient id="langBarGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%"   stopColor="#8B5CF6" stopOpacity={1}    />
                  <stop offset="100%" stopColor="#6366F1" stopOpacity={0.72} />
                </linearGradient>
              </defs>
              <XAxis dataKey="name" tick={TICK} {...AXIS_LINE} />
              <YAxis               tick={TICK} {...AXIS_LINE} />
              <Tooltip {...TOOLTIP_STYLE} />
              <Bar dataKey="value" fill="url(#langBarGrad)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        {/* Queries by City — blue gradient bars */}
        <Card padding="p-5" className="card-important">
          <div className="label mb-4">Queries by City</div>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={cityData}>
              <defs>
                <linearGradient id="cityBarGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%"   stopColor="#60A5FA" stopOpacity={1}    />
                  <stop offset="100%" stopColor="#3B82F6" stopOpacity={0.72} />
                </linearGradient>
              </defs>
              <XAxis dataKey="name" tick={TICK} {...AXIS_LINE} />
              <YAxis               tick={TICK} {...AXIS_LINE} />
              <Tooltip {...TOOLTIP_STYLE} />
              <Bar dataKey="value" fill="url(#cityBarGrad)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* Application Status Breakdown */}
      {appStats.by_status && (
        <Card padding="p-5" className="card-important">
          <div className="label mb-4">Application Status Breakdown</div>
          <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
            {Object.entries(appStats.by_status).map(([status, count]) => (
              <div
                key={status}
                className="text-center rounded-xl p-3 card"
              >
                <div className="font-display text-2xl font-semibold" style={{ color: 'var(--text-primary)' }}>
                  {count}
                </div>
                <div className="text-xs capitalize mt-1" style={{ color: 'var(--text-muted)' }}>
                  {status.replace('_', ' ')}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </PageContainer>
  )
}
