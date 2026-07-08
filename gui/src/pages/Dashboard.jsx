import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useFetch } from '../hooks/useFetch';
import { LayoutDashboard, AlertTriangle, Clock, XCircle, CheckCircle2, Plus } from 'lucide-react';

const API = 'http://localhost:8000/api';

export function Dashboard() {
  const { data: courses, loading, refresh } = useFetch(`${API}/courses`);
  const { data: usage } = useFetch(`${API}/usage`);
  const { data: alerts } = useFetch(`${API}/alerts`);

  const [showModal, setShowModal] = useState(false);
  const [newCourse, setNewCourse] = useState({ title: '', topic: '', target_audience: 'beginners', difficulty: 'mixed' });

  const stats = courses ? {
    courses: courses.length,
    done: courses.reduce((s, c) => s + c.done_lessons, 0),
    processing: courses.reduce((s, c) => s + c.processing_lessons, 0),
    failed: courses.reduce((s, c) => s + c.failed_lessons, 0),
  } : {};

  const handleCreateCourse = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API}/courses`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newCourse)
      });
      if(res.ok) {
        setShowModal(false);
        refresh();
      }
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <header className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <LayoutDashboard className="w-6 h-6 text-zinc-400" />
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        </div>
        <button onClick={() => setShowModal(true)} className="flex items-center gap-2 bg-white text-black px-4 py-2 rounded-md font-medium hover:bg-zinc-200 transition-colors">
          <Plus className="w-4 h-4" /> New Course
        </button>
      </header>

      {alerts?.failed_lessons > 0 && (
        <div className="mb-6 p-4 bg-red-950/30 border border-red-900/50 rounded-lg flex items-start gap-3 text-red-200">
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
          <div>
            <strong className="font-medium">Action Required:</strong> {alerts.failed_lessons} lesson(s) failed generation.
            Check the Pipeline Monitor for details.
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-10">
        <div className="bg-zinc-900/50 border border-zinc-800 p-5 rounded-xl">
          <div className="text-zinc-400 text-sm font-medium mb-1">Total Courses</div>
          <div className="text-3xl font-semibold">{loading ? '...' : stats.courses}</div>
        </div>
        <div className="bg-zinc-900/50 border border-zinc-800 p-5 rounded-xl">
          <div className="text-zinc-400 text-sm font-medium mb-1">Videos Produced</div>
          <div className="text-3xl font-semibold text-zinc-100">{loading ? '...' : stats.done}</div>
        </div>
        <div className="bg-zinc-900/50 border border-zinc-800 p-5 rounded-xl">
          <div className="text-zinc-400 text-sm font-medium mb-1">Processing</div>
          <div className="text-3xl font-semibold text-yellow-500">{loading ? '...' : stats.processing}</div>
        </div>
        <div className="bg-zinc-900/50 border border-zinc-800 p-5 rounded-xl">
          <div className="text-zinc-400 text-sm font-medium mb-1">API Cost (USD)</div>
          <div className="text-3xl font-semibold text-zinc-100">${usage?.total_cost_usd?.toFixed(4) || '0.0000'}</div>
        </div>
      </div>

      <h2 className="text-xl font-medium tracking-tight mb-4">Active Curricula</h2>
      <div className="border border-zinc-800 rounded-xl overflow-hidden bg-zinc-900/20">
        {loading ? (
          <div className="p-8 text-center text-zinc-500">Loading courses...</div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="bg-zinc-900/50 border-b border-zinc-800 text-zinc-400">
              <tr>
                <th className="px-6 py-4 font-medium">Course Title</th>
                <th className="px-6 py-4 font-medium">Target Audience</th>
                <th className="px-6 py-4 font-medium">Progress</th>
                <th className="px-6 py-4 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/50">
              {courses?.map(c => {
                const pct = c.total_lessons > 0 ? Math.round((c.done_lessons / c.total_lessons) * 100) : 0;
                return (
                  <tr key={c.id} className="hover:bg-zinc-900/30 transition-colors">
                    <td className="px-6 py-4 font-medium">{c.title}</td>
                    <td className="px-6 py-4 text-zinc-400">{c.target_audience || 'Beginners'}</td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="h-1.5 flex-1 bg-zinc-800 rounded-full overflow-hidden">
                          <div className="h-full bg-white rounded-full" style={{ width: `${pct}%` }} />
                        </div>
                        <span className="text-xs text-zinc-500 w-12 text-right">{c.done_lessons} / {c.total_lessons}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <Link to={`/curricula/${c.id}`} className="inline-flex items-center justify-center px-3 py-1.5 border border-zinc-700 rounded-md text-zinc-300 hover:bg-zinc-800 hover:text-white transition-colors">
                        View
                      </Link>
                    </td>
                  </tr>
                )
              })}
              {courses?.length === 0 && (
                <tr>
                  <td colSpan="4" className="px-6 py-12 text-center text-zinc-500">
                    No courses created yet. Click "New Course" to get started.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-6 w-full max-w-md shadow-2xl">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-medium">Create New Course</h3>
              <button onClick={() => setShowModal(false)} className="text-zinc-500 hover:text-white">✕</button>
            </div>
            <form onSubmit={handleCreateCourse} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-zinc-400 mb-1.5">Course Title</label>
                <input required type="text" className="w-full bg-zinc-900 border border-zinc-800 rounded-md px-3 py-2 text-white focus:outline-none focus:border-zinc-500" value={newCourse.title} onChange={e => setNewCourse({...newCourse, title: e.target.value})} placeholder="e.g. Master React in 30 Days" />
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-400 mb-1.5">Topic</label>
                <input required type="text" className="w-full bg-zinc-900 border border-zinc-800 rounded-md px-3 py-2 text-white focus:outline-none focus:border-zinc-500" value={newCourse.topic} onChange={e => setNewCourse({...newCourse, topic: e.target.value})} placeholder="e.g. React.js" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-zinc-400 mb-1.5">Audience</label>
                  <select className="w-full bg-zinc-900 border border-zinc-800 rounded-md px-3 py-2 text-white focus:outline-none focus:border-zinc-500" value={newCourse.target_audience} onChange={e => setNewCourse({...newCourse, target_audience: e.target.value})}>
                    <option value="beginners">Beginners</option>
                    <option value="intermediate">Intermediate</option>
                    <option value="advanced">Advanced</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-zinc-400 mb-1.5">Difficulty</label>
                  <select className="w-full bg-zinc-900 border border-zinc-800 rounded-md px-3 py-2 text-white focus:outline-none focus:border-zinc-500" value={newCourse.difficulty} onChange={e => setNewCourse({...newCourse, difficulty: e.target.value})}>
                    <option value="mixed">Mixed</option>
                    <option value="beginner">Beginner</option>
                    <option value="advanced">Advanced</option>
                  </select>
                </div>
              </div>
              <div className="pt-4 flex justify-end gap-3">
                <button type="button" onClick={() => setShowModal(false)} className="px-4 py-2 rounded-md font-medium text-zinc-400 hover:text-white transition-colors">Cancel</button>
                <button type="submit" className="px-4 py-2 bg-white text-black rounded-md font-medium hover:bg-zinc-200 transition-colors">Create</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
