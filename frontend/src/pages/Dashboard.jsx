import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { getDashboardStats } from "../api";
import {
  Users,
  UserCheck,
  UserX,
  Contact,
  Clock,
  AlertTriangle,
  TriangleAlert,
} from "lucide-react";

function StatCard({ label, value, icon: Icon, tone }) {
  const tones = {
    accent: { bg: "var(--accent-soft)", fg: "var(--accent)" },
    success: { bg: "var(--success-soft)", fg: "var(--success)" },
    danger: { bg: "var(--danger-soft)", fg: "var(--danger)" },
    teal: { bg: "var(--teal-soft)", fg: "var(--teal)" },
    warning: { bg: "var(--warning-soft)", fg: "var(--warning)" },
  };
  const t = tones[tone] || tones.accent;
  return (
    <div className="stat-card">
      <div className="stat-card-text">
        <span className="stat-label">{label}</span>
        <span className="stat-value">{value}</span>
      </div>
      <div className="stat-icon" style={{ background: t.bg, color: t.fg }}>
        <Icon size={19} strokeWidth={2} />
      </div>
    </div>
  );
}

function Dashboard() {
  const [stats, setStats] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getDashboardStats().then(setStats).catch((e) => setError(e.message));
  }, []);

  if (error) {
    return (
      <div className="alert alert-danger">
        <AlertTriangle size={16} /> Could not load dashboard: {error}
      </div>
    );
  }
  if (!stats) return <p>Loading…</p>;

  return (
    <div>
      <div className="stat-grid">
        <StatCard label="Total employees" value={stats.total_employees} icon={Users} tone="accent" />
        <StatCard label="Attended today" value={stats.attended_today} icon={UserCheck} tone="success" />
        <StatCard label="Absent today" value={stats.absent_today} icon={UserX} tone="danger" />
        <StatCard label="Visitors this month" value={stats.visitors_this_month} icon={Contact} tone="teal" />
      </div>

      <div className="stat-grid" style={{ marginTop: 14 }}>
        <StatCard label="On-time % (all-time)" value={`${stats.on_time_pct}%`} icon={Clock} tone="accent" />
        <StatCard label="Late % (all-time)" value={`${stats.late_pct}%`} icon={TriangleAlert} tone="warning" />
        <StatCard label="Total visitors (all-time)" value={stats.total_visitors_all_time} icon={Contact} tone="teal" />
      </div>

      <div className="chart-row">
        <div className="chart-card">
          <h3>Most attending employees</h3>
          {stats.top_attendees.length === 0 ? <p>No data yet.</p> : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={stats.top_attendees}>
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="count" fill="#2A5CE0" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="chart-card">
          <h3>Most attending by work hours</h3>
          {stats.top_by_hours.length === 0 ? <p>No completed check-outs yet.</p> : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={stats.top_by_hours}>
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis />
                <Tooltip />
                <Bar dataKey="hours" fill="#148A4A" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      <div className="chart-card" style={{ marginTop: 16 }}>
        <h3>Attendance by department</h3>
        {stats.by_department.length === 0 ? <p>No data yet.</p> : (
          <div className="dept-grid">
            {stats.by_department.map((d) => (
              <div key={d.department} className="dept-tile">
                <div className="dept-count">{d.count}</div>
                <div className="dept-name">{d.department}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default Dashboard;
