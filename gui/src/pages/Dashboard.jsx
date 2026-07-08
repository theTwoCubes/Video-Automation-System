import { Link } from 'react-router-dom';
import { useFetch } from '../hooks/useFetch';
import { LayoutDashboard, AlertTriangle, BookOpen, Clock, XCircle, CheckCircle2 } from 'lucide-react';

const API = 'http://localhost:8000/api';

function StatusBadge({ status }) {
  const map = {
    done: { cls: 'badge-done', icon: <CheckCircle2 size={12} /> },
    pending: { cls: 'badge-pending', icon: <Clock size={12} /> },
    processing: { cls: 'badge-processing', icon: <Clock size={12} /> },
    failed: { cls: 'badge-failed', icon: <XCircle size={12} /> },
  };
  const { cls, icon } = map[status] || map.pending;
  return <span className={`badge ${cls}`}>{icon} {status}</span>;
}

export function Dashboard() {
  const { data: courses, loading } = useFetch(`${API}/courses`);
  const { data: usage } = useFetch(`${API}/usage`);
  const { data: alerts } = useFetch(`${API}/alerts`);

  const stats = courses ? {
    courses: courses.length,
    done: courses.reduce((s, c) => s + c.done_lessons, 0),
    processing: courses.reduce((s, c) => s + c.processing_lessons, 0),
    failed: courses.reduce((s, c) => s + c.failed_lessons, 0),
  } : {};

  return (
    <div className="main">
      <header className="topbar">
        <LayoutDashboard size={18} />
        <h1 className="topbar-title">Dashboard</h1>
      </header>

      <main className="content">
        {alerts?.failed_lessons > 0 && (
          <div className="alert-banner error">
            <AlertTriangle size={18} />
            <div>
              <strong>Action Required:</strong> {alerts.failed_lessons} lesson(s) failed generation.
              Check the Pipeline Monitor for details.
            </div>
          </div>
        )}

        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-label">Total Courses</div>
            <div className="stat-value">{loading ? '...' : stats.courses}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Videos Produced</div>
            <div className="stat-value success">{loading ? '...' : stats.done}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Processing</div>
            <div className="stat-value warning">{loading ? '...' : stats.processing}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">API Cost (USD)</div>
            <div className="stat-value info">${usage?.total_cost_usd?.toFixed(4) || '0.0000'}</div>
          </div>
        </div>

        <h2 className="section-title">Active Curricula</h2>
        <div className="card">
          {loading ? (
            <div className="loading">Loading courses...</div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Course Title</th>
                  <th>Target Audience</th>
                  <th>Progress</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {courses?.map(c => {
                  const pct = c.total_lessons > 0 ? Math.round((c.done_lessons / c.total_lessons) * 100) : 0;
                  return (
                    <tr key={c.id}>
                      <td className="strong">{c.title}</td>
                      <td><span className="badge">{c.target_audience || 'Beginners'}</span></td>
                      <td>
                        <div className="progress-bar">
                          <div className="progress-fill success" style={{ width: `${pct}%` }} />
                        </div>
                        <span className="text-small text-dim mt-1">{c.done_lessons} / {c.total_lessons} done</span>
                      </td>
                      <td>
                        <Link to={`/curricula/${c.id}`} className="btn btn-outline btn-sm">View</Link>
                      </td>
                    </tr>
                  )
                })}
                {courses?.length === 0 && (
                  <tr><td colSpan="4" className="text-center text-dim py-4">No curricula generated yet.</td></tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      </main>
    </div>
  );
}
