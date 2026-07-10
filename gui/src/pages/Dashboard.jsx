import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useFetch } from '../hooks/useFetch';

const API = 'http://localhost:8000/api';
const cx = (...a) => a.filter(Boolean).join(' ');

const S = {
  label: 'text-[10px] font-bold text-teal-400 uppercase tracking-[0.15em] mb-1.5 block',
  card:  'bg-[#0d0d0d] border border-[#1a1a1a] rounded-xl',
  input: 'w-full bg-[#111] border border-[#222] rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-teal-500 transition-colors',
};

function StatCard({ value, label, color = 'text-white' }) {
  return (
    <div className={cx(S.card, 'px-5 py-4 flex flex-col gap-1')}>
      <div className={cx('text-3xl font-bold tabular-nums', color)}>{value ?? '-'}</div>
      <div className="text-[11px] text-zinc-600 uppercase tracking-wider font-medium">{label}</div>
    </div>
  );
}



function CourseCard({ course }) {
  const totalLessons = (course.done_lessons || 0) + (course.processing_lessons || 0)
    + (course.failed_lessons || 0) + (course.pending_lessons || 0);
  const pct = totalLessons > 0 ? Math.round((course.done_lessons / totalLessons) * 100) : 0;

  return (
    <Link to={`/curricula/${course.id}`} className={cx(S.card, 'block px-5 py-4 hover:border-[#2a2a2a] transition-all duration-150 group')}>
      <div className="flex items-start justify-between gap-2 mb-3">
        <div>
          <div className="text-[13px] font-semibold text-white group-hover:text-teal-300 transition-colors">{course.title}</div>
          <div className="text-[11px] text-zinc-600 mt-0.5">{course.topic || course.id}</div>
        </div>
        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#111] border border-[#222] text-zinc-500 flex-shrink-0">
          {pct}%
        </span>
      </div>
      {/* progress bar */}
      <div className="h-1 bg-[#1a1a1a] rounded-full overflow-hidden mb-3">
        <div
          className="h-full bg-teal-500 rounded-full transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="flex gap-4 text-[11px]">
        <span className="flex items-center gap-1.5 text-emerald-400">
          <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full" />
          {course.done_lessons || 0} done
        </span>
        {(course.processing_lessons || 0) > 0 && (
          <span className="flex items-center gap-1.5 text-amber-400">
            <span className="w-1.5 h-1.5 bg-amber-400 animate-pulse rounded-full" />
            {course.processing_lessons} running
          </span>
        )}
        {(course.failed_lessons || 0) > 0 && (
          <span className="flex items-center gap-1.5 text-red-400">
            <span className="w-1.5 h-1.5 bg-red-400 rounded-full" />
            {course.failed_lessons} failed
          </span>
        )}
        <span className="text-zinc-600 ml-auto">{totalLessons} total</span>
      </div>
    </Link>
  );
}

export function Dashboard() {
  const { data: courses, loading, refresh } = useFetch(`${API}/courses`);
  const { data: usage }  = useFetch(`${API}/usage`);
  const { data: alerts } = useFetch(`${API}/alerts`);

  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({
    title: '', topic: '', target_audience: 'beginners', difficulty: 'mixed',
  });
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');

  const stats = courses ? {
    courses:    courses.length,
    done:       courses.reduce((s, c) => s + (c.done_lessons || 0), 0),
    processing: courses.reduce((s, c) => s + (c.processing_lessons || 0), 0),
    failed:     courses.reduce((s, c) => s + (c.failed_lessons || 0), 0),
  } : {};

  async function handleCreate(e) {
    e.preventDefault();
    if (!form.title.trim() || !form.topic.trim()) { setError('Title and topic are required.'); return; }
    setCreating(true); setError('');
    try {
      const res = await fetch(`${API}/courses`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      if (res.ok) { setShowModal(false); setForm({ title: '', topic: '', target_audience: 'beginners', difficulty: 'mixed' }); refresh(); }
      else        { setError('Failed to create course.'); }
    } catch { setError('Network error.'); }
    finally  { setCreating(false); }
  }

  return (
    <div className="min-h-screen bg-black text-zinc-200 p-8" style={{ fontFamily: "'Inter', sans-serif" }}>
      <div className="max-w-6xl mx-auto space-y-8">

        {/* Header */}
        <div className="flex items-end justify-between">
          <div>
            <div className="flex items-center gap-2.5 mb-1">
              <div className="w-1.5 h-5 bg-teal-400 rounded-full" />
              <h1 className="text-xl font-bold text-white tracking-tight">Dashboard</h1>
            </div>
            <p className="text-zinc-600 text-[13px] ml-4">Overview of all courses and lesson generation.</p>
          </div>
          <button
            onClick={() => setShowModal(true)}
            className="flex items-center gap-2 bg-teal-500 hover:bg-teal-400 text-black text-[13px] font-bold px-4 py-2.5 rounded-xl transition-all active:scale-95"
          >
            <span className="text-base leading-none">+</span>
            New Course
          </button>
        </div>

        {/* Alert banner */}
        {alerts?.failed_lessons > 0 && (
          <div className="p-4 bg-red-500/5 border border-red-500/20 rounded-xl flex items-start gap-3 text-red-300 text-[13px]">
            <span className="text-base mt-0.5">⚠</span>
            <div>
              <strong className="font-semibold">Action required:</strong>{' '}
              {alerts.failed_lessons} lesson(s) failed.{' '}
              <Link to="/pipeline" className="text-red-400 hover:text-red-300 underline underline-offset-2">
                View Pipeline Monitor
              </Link>
            </div>
          </div>
        )}

        {/* Stat cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard value={stats.courses}    label="Courses"    />
          <StatCard value={stats.done}       label="Lessons Done"    color="text-emerald-400" />
          <StatCard value={stats.processing} label="Processing" color="text-amber-400" />
          <StatCard value={stats.failed}     label="Failed"     color="text-red-400" />
        </div>

        {/* Usage */}
        {usage && (
          <div className={cx(S.card, 'px-5 py-4 flex items-center gap-8 flex-wrap')}>
            <span className={S.label} style={{ marginBottom: 0 }}>LLM Usage</span>
            {Object.entries(usage).map(([k, v]) => (
              <div key={k} className="text-[12px]">
                <span className="text-zinc-500">{k}: </span>
                <span className="text-zinc-200 font-medium tabular-nums">{typeof v === 'number' ? v.toLocaleString() : v}</span>
              </div>
            ))}
          </div>
        )}

        {/* Course grid */}
        <div>
          <span className={S.label}>Active Courses</span>
          {loading && (
            <div className="text-zinc-700 text-[13px] mt-4">Loading courses...</div>
          )}
          {!loading && !courses?.length && (
            <div className={cx(S.card, 'px-6 py-12 text-center')}>
              <div className="text-4xl mb-3">📂</div>
              <div className="text-zinc-400 font-medium">No courses yet</div>
              <div className="text-zinc-700 text-[13px] mt-1">Create your first course to get started.</div>
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 mt-3">
            {(courses || []).map(c => <CourseCard key={c.id} course={c} />)}
          </div>
        </div>
      </div>

      {/* Create Course Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className={cx(S.card, 'w-full max-w-md p-6 space-y-5')}>
            <div className="flex items-center justify-between">
              <h2 className="text-base font-bold text-white">New Course</h2>
              <button onClick={() => setShowModal(false)} className="text-zinc-600 hover:text-zinc-300 text-lg leading-none">×</button>
            </div>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <span className={S.label}>Course Title</span>
                <input className={S.input} placeholder="e.g. Modern C++ for Beginners"
                  value={form.title} onChange={e => setForm(p => ({ ...p, title: e.target.value }))} />
              </div>
              <div>
                <span className={S.label}>Topic / Description</span>
                <textarea className={cx(S.input, 'resize-none h-20')} placeholder="Describe the course content..."
                  value={form.topic} onChange={e => setForm(p => ({ ...p, topic: e.target.value }))} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <span className={S.label}>Audience</span>
                  <select className={S.input} value={form.target_audience}
                    onChange={e => setForm(p => ({ ...p, target_audience: e.target.value }))}>
                    <option value="beginners">Beginners</option>
                    <option value="intermediate">Intermediate</option>
                    <option value="advanced">Advanced</option>
                  </select>
                </div>
                <div>
                  <span className={S.label}>Difficulty</span>
                  <select className={S.input} value={form.difficulty}
                    onChange={e => setForm(p => ({ ...p, difficulty: e.target.value }))}>
                    <option value="mixed">Mixed</option>
                    <option value="beginner">Beginner</option>
                    <option value="intermediate">Intermediate</option>
                    <option value="advanced">Advanced</option>
                  </select>
                </div>
              </div>
              {error && <div className="text-red-400 text-[12px]">{error}</div>}
              <div className="flex gap-3 pt-1">
                <button type="button" onClick={() => setShowModal(false)}
                  className="flex-1 py-2.5 rounded-lg text-[13px] font-medium bg-[#111] text-zinc-400 border border-[#222] hover:border-[#333] transition-colors">
                  Cancel
                </button>
                <button type="submit" disabled={creating}
                  className="flex-1 py-2.5 rounded-lg text-[13px] font-bold bg-teal-500 hover:bg-teal-400 text-black transition-colors disabled:opacity-50">
                  {creating ? 'Creating...' : 'Create Course'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
