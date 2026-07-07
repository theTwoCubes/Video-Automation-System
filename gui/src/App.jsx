import { useState, useEffect, useCallback } from 'react'
import { BrowserRouter, Routes, Route, NavLink, useNavigate, useParams } from 'react-router-dom'
import {
  LayoutDashboard, BookOpen, DollarSign, FlaskConical,
  CheckCircle2, Clock, Loader2, XCircle, ChevronRight,
  ArrowLeft, Sparkles, Play, RefreshCw, FileJson,
  AlertTriangle, Video, Terminal
} from 'lucide-react'
import './index.css'

const API = 'http://localhost:8000/api'

// ── helpers ──────────────────────────────────────────────────────

function useFetch(url, deps = []) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(() => {
    if (!url) return
    setLoading(true)
    fetch(url)
      .then(r => { if (!r.ok) throw new Error(`${r.status}`); return r.json() })
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [url, ...deps])

  useEffect(() => { load() }, [load])
  return { data, loading, error, refresh: load }
}

function usePolling(url, intervalMs = 2000, enabled = true) {
  const [data, setData] = useState(null)
  useEffect(() => {
    if (!enabled || !url) return
    const tick = () => fetch(url).then(r => r.json()).then(setData).catch(() => {})
    tick()
    const id = setInterval(tick, intervalMs)
    return () => clearInterval(id)
  }, [url, intervalMs, enabled])
  return data
}

// ── components ────────────────────────────────────────────────────

function StatusBadge({ status }) {
  const map = {
    done:       { cls: 'badge-done',       icon: <CheckCircle2 size={10} /> },
    pending:    { cls: 'badge-pending',    icon: <Clock size={10} /> },
    processing: { cls: 'badge-processing', icon: <Loader2 size={10} className="spin" /> },
    running:    { cls: 'badge-processing', icon: <Loader2 size={10} className="spin" /> },
    failed:     { cls: 'badge-failed',     icon: <XCircle size={10} /> },
  }
  const { cls, icon } = map[status] || map.pending
  return <span className={`badge ${cls}`}>{icon} {status}</span>
}

function QAScore({ score }) {
  if (!score) return <span className="qa-score low">—</span>
  return <span className={`qa-score ${score >= 90 ? 'high' : score >= 70 ? 'mid' : 'low'}`}>{score}/100</span>
}

const PIPELINE_STEPS = ['Plan', 'Script', 'Code', 'Diagrams', 'Slides', 'Voice', 'Video', 'Thumbnail', 'QA', 'SEO']

function PipelineDiagram({ completedSteps = 0, status = 'done' }) {
  return (
    <div className="pipeline-diagram">
      {PIPELINE_STEPS.map((step, i) => {
        const s = i < completedSteps ? 'done' : (i === completedSteps && status === 'processing') ? 'active' : 'pending'
        return (
          <div key={step} style={{ display: 'flex', alignItems: 'center' }}>
            <div className="pipe-step">
              <div className={`pipe-dot ${s}`}>{s === 'done' ? '✓' : s === 'active' ? '⋯' : i + 1}</div>
              <div className="pipe-label">{step}</div>
            </div>
            {i < PIPELINE_STEPS.length - 1 && <div className={`pipe-connector ${s === 'done' ? 'done' : ''}`} />}
          </div>
        )
      })}
    </div>
  )
}

// ── Dashboard ─────────────────────────────────────────────────────

function Dashboard() {
  const navigate = useNavigate()
  const { data: courses, loading } = useFetch(`${API}/courses`)
  const { data: usage } = useFetch(`${API}/usage`)
  const { data: testRuns } = useFetch(`${API}/test/runs`)

  const stats = courses ? {
    courses: courses.length,
    done: courses.reduce((s, c) => s + c.done_lessons, 0),
    processing: courses.reduce((s, c) => s + c.processing_lessons, 0),
    failed: courses.reduce((s, c) => s + c.failed_lessons, 0),
  } : {}

  const recentTest = testRuns?.[testRuns.length - 1]

  return (
    <div>
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">Courses</div>
          <div className="stat-value">{loading ? '—' : stats.courses ?? 0}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Videos Done</div>
          <div className="stat-value green">{loading ? '—' : stats.done ?? 0}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Total Cost</div>
          <div className="stat-value">₹{usage?.total_cost_inr?.toFixed(2) ?? '0.00'}</div>
        </div>
        <div className="stat-card" style={{ cursor: 'pointer' }} onClick={() => navigate('/test')}>
          <div className="stat-label">Last Test</div>
          <div className="stat-value" style={{ fontSize: 20 }}>
            {recentTest ? <StatusBadge status={recentTest.status} /> : <span style={{ color: 'var(--text-muted)', fontSize: 16 }}>No runs yet</span>}
          </div>
        </div>
      </div>

      <h2 style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 14, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
        Courses
      </h2>
      {loading && <div className="empty"><Loader2 size={20} className="spin" /></div>}
      {!loading && courses?.length === 0 && (
        <div className="empty"><BookOpen size={36} /><p style={{ marginTop: 12 }}>No courses. Ingest a book to start.</p></div>
      )}
      <div className="course-grid">
        {courses?.map(c => <CourseCard key={c.id} course={c} />)}
      </div>
    </div>
  )
}

function CourseCard({ course }) {
  const navigate = useNavigate()
  const pct = course.total_lessons ? Math.round((course.done_lessons / course.total_lessons) * 100) : 0
  return (
    <div className="course-card" onClick={() => navigate(`/courses/${course.id}`)}>
      <div className="course-title">{course.title}</div>
      <div className="course-meta">{course.target_audience} · {course.total_lessons} lessons</div>
      <div className="progress-bar-wrap"><div className="progress-bar-fill" style={{ width: `${pct}%` }} /></div>
      <div className="progress-label">{pct}% — {course.done_lessons}/{course.total_lessons} done</div>
      <div style={{ display: 'flex', gap: 8, marginTop: 14, flexWrap: 'wrap' }}>
        {course.done_lessons > 0 && <StatusBadge status="done" />}
        {course.processing_lessons > 0 && <StatusBadge status="processing" />}
        {course.failed_lessons > 0 && <StatusBadge status="failed" />}
      </div>
    </div>
  )
}

// ── Course Page ───────────────────────────────────────────────────

function CoursePage() {
  const { courseId } = useParams()
  const navigate = useNavigate()
  const { data, loading, error } = useFetch(`${API}/courses/${courseId}/lessons`, [courseId])
  const [generating, setGenerating] = useState(false)
  const [filter, setFilter] = useState('all')

  const handleGenerate = async () => {
    setGenerating(true)
    await fetch(`${API}/courses/${courseId}/generate`, { method: 'POST' })
    setTimeout(() => setGenerating(false), 2000)
  }

  const lessons = data?.lessons?.filter(l => filter === 'all' || l.status === filter) ?? []

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <button className="btn btn-ghost btn-sm" onClick={() => navigate('/')}><ArrowLeft size={14} /> Back</button>
        <h1 style={{ fontSize: 20, fontWeight: 700 }}>{data?.course?.title ?? '...'}</h1>
        <div style={{ flex: 1 }} />
        <button className="btn btn-primary" onClick={handleGenerate} disabled={generating}>
          {generating ? <Loader2 size={14} className="spin" /> : <Sparkles size={14} />}
          {generating ? 'Starting...' : 'Generate Next Video'}
        </button>
      </div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 18 }}>
        {['all', 'done', 'processing', 'pending', 'failed'].map(f => (
          <button key={f} className="btn btn-ghost btn-sm" onClick={() => setFilter(f)}
            style={filter === f ? { borderColor: 'var(--accent)', color: 'var(--accent)' } : {}}>
            {f}
          </button>
        ))}
      </div>
      {loading && <div className="empty"><Loader2 size={20} className="spin" /></div>}
      {error && <div className="empty" style={{ color: 'var(--red)' }}>{error}</div>}
      {!loading && (
        <div className="card">
          <table className="lesson-table">
            <thead><tr><th>#</th><th>Title</th><th>Status</th><th>QA</th><th>SEO Title</th><th></th></tr></thead>
            <tbody>
              {lessons.map(l => (
                <tr key={l.id} onClick={() => navigate(`/lessons/${l.id}`)} style={{ cursor: 'pointer' }}>
                  <td><span className="lesson-num">{String(l.position).padStart(3, '0')}</span></td>
                  <td><span className="lesson-title">{l.title}</span></td>
                  <td><StatusBadge status={l.status} /></td>
                  <td><QAScore score={l.qa_score} /></td>
                  <td style={{ color: 'var(--text-dim)', maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{l.seo_title || '—'}</td>
                  <td><ChevronRight size={14} style={{ color: 'var(--text-muted)' }} /></td>
                </tr>
              ))}
              {lessons.length === 0 && (
                <tr><td colSpan={6} style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>No lessons match filter.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Lesson Page ───────────────────────────────────────────────────

function LessonPage() {
  const { lessonId } = useParams()
  const navigate = useNavigate()
  const { data, loading } = useFetch(`${API}/lessons/${lessonId}/slides`, [lessonId])
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <button className="btn btn-ghost btn-sm" onClick={() => navigate(-1)}><ArrowLeft size={14} /> Back</button>
        <h1 style={{ fontSize: 18, fontWeight: 700 }}>Lesson Detail</h1>
      </div>
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-title">Pipeline Stages</div>
        <PipelineDiagram status="done" completedSteps={10} />
      </div>
      <div className="card">
        <div className="card-title">Slides ({data?.slides?.length ?? 0})</div>
        {loading && <div className="empty"><Loader2 size={20} className="spin" /></div>}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 10 }}>
          {data?.slides?.map((s, i) => (
            <div key={i} style={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 8, padding: 8 }}>
              <div style={{ background: 'var(--surface)', borderRadius: 6, aspectRatio: '16/9', marginBottom: 6, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: 12 }}>
                Slide {i + 1}
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', wordBreak: 'break-all' }}>
                {s.split(/[\\/]/).pop()}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Cost Page ─────────────────────────────────────────────────────

function CostPage() {
  const { data, loading } = useFetch(`${API}/usage`)
  return (
    <div>
      <div className="stats-grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
        <div className="stat-card">
          <div className="stat-label">Total Cost (USD)</div>
          <div className="stat-value">${loading ? '—' : (data?.total_cost_usd?.toFixed(4) ?? '0.0000')}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Total Cost (INR)</div>
          <div className="stat-value green">₹{loading ? '—' : (data?.total_cost_inr?.toFixed(2) ?? '0.00')}</div>
        </div>
      </div>
      <div className="card">
        <div className="card-title">Per Model</div>
        {loading && <div className="empty"><Loader2 size={20} className="spin" /></div>}
        {!loading && data?.models?.length === 0 && <div className="empty"><p>No usage recorded.</p></div>}
        {data?.models?.map(m => (
          <div key={m.model} style={{ marginBottom: 16, paddingBottom: 16, borderBottom: '1px solid var(--border)' }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>{m.model}</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
              {[['API Calls', m.calls], ['Input Tokens', m.input_tokens?.toLocaleString()], ['Output Tokens', m.output_tokens?.toLocaleString()]].map(([label, val]) => (
                <div key={label} style={{ background: 'var(--surface2)', borderRadius: 8, padding: '10px 14px' }}>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>{label}</div>
                  <div style={{ fontWeight: 600 }}>{val}</div>
                </div>
              ))}
            </div>
            <div style={{ marginTop: 8, color: 'var(--accent)', fontWeight: 600 }}>${m.cost_usd?.toFixed(6)} · ₹{m.cost_inr?.toFixed(4)}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Test Runner Page ──────────────────────────────────────────────

function TestPage() {
  const { data: fixtures, loading: fixturesLoading } = useFetch(`${API}/test/fixtures`)
  const [selected, setSelected] = useState('tests/fixtures/cpp_variables_lesson.json')
  const [forceRestart, setForceRestart] = useState(false)
  const [launching, setLaunching] = useState(false)
  const [activeRunId, setActiveRunId] = useState(null)

  // poll run status while a run is active
  const runData = usePolling(
    activeRunId ? `${API}/test/runs/${activeRunId}` : null,
    1500,
    !!activeRunId && true
  )

  // stop polling when done/failed
  useEffect(() => {
    if (runData?.status === 'done' || runData?.status === 'failed') {
      // keep showing final state but stop polling after 1 more second
      setTimeout(() => {}, 1000)
    }
  }, [runData?.status])

  const { data: allRuns } = useFetch(`${API}/test/runs`)

  const handleRun = async () => {
    setLaunching(true)
    try {
      const res = await fetch(`${API}/test/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fixture_path: selected, force_restart: forceRestart }),
      })
      const data = await res.json()
      setActiveRunId(data.run_id)
    } catch (e) {
      alert('Failed to start test: ' + e.message)
    }
    setLaunching(false)
  }

  const activeRun = runData || allRuns?.find(r => r.id === activeRunId)
  const isRunning = activeRun?.status === 'running'

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 6 }}>Test Pipeline Runner</h2>
        <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>
          Run the complete rendering pipeline using pre-captured fixture data. Zero LLM calls — verifies slide rendering, audio synthesis, and video composition after every code change.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>

        {/* Fixture selector */}
        <div className="card">
          <div className="card-title">Select Fixture</div>
          {fixturesLoading && <div className="empty"><Loader2 size={16} className="spin" /></div>}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {fixtures?.map(fx => (
              <div
                key={fx.path}
                onClick={() => setSelected(fx.path)}
                style={{
                  padding: '12px 16px', borderRadius: 8,
                  border: `1px solid ${selected === fx.path ? 'var(--accent)' : 'var(--border)'}`,
                  background: selected === fx.path ? 'rgba(0,200,150,0.05)' : 'var(--surface2)',
                  cursor: 'pointer', transition: 'all 0.15s',
                }}
              >
                <div style={{ fontWeight: 600, fontSize: 13, color: selected === fx.path ? 'var(--accent)' : 'var(--text)' }}>
                  <FileJson size={13} style={{ marginRight: 6, verticalAlign: 'middle' }} />
                  {fx.lesson_title}
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                  {fx.slides} slides · {fx.script_segments} script segments · {fx.name}
                </div>
              </div>
            ))}
            {!fixturesLoading && fixtures?.length === 0 && (
              <div className="empty" style={{ padding: 20 }}>
                <p>No fixtures found in tests/fixtures/</p>
                <p style={{ marginTop: 8, fontSize: 12 }}>Run a real pipeline first, then: <code style={{ color: 'var(--accent)' }}>python scripts/capture_fixtures.py --lesson-id &lt;id&gt;</code></p>
              </div>
            )}
          </div>

          <div style={{ marginTop: 16, display: 'flex', alignItems: 'center', gap: 10 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 13, color: 'var(--text-dim)' }}>
              <input
                type="checkbox" checked={forceRestart} onChange={e => setForceRestart(e.target.checked)}
                style={{ accentColor: 'var(--accent)' }}
              />
              Force restart (clear cache)
            </label>
            <div style={{ flex: 1 }} />
            <button
              className="btn btn-primary"
              onClick={handleRun}
              disabled={launching || isRunning || !selected}
            >
              {launching || isRunning
                ? <><Loader2 size={14} className="spin" /> Running...</>
                : <><Play size={14} /> Run Test</>}
            </button>
          </div>
        </div>

        {/* Active run status */}
        <div className="card">
          <div className="card-title">Current Run</div>
          {!activeRun && (
            <div className="empty" style={{ padding: 30 }}>
              <FlaskConical size={28} style={{ opacity: 0.3, marginBottom: 10 }} />
              <p>Select a fixture and click Run Test</p>
            </div>
          )}
          {activeRun && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
                <StatusBadge status={activeRun.status} />
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  {activeRun.id} · started {activeRun.started_at?.slice(11, 19)}
                </span>
              </div>

              {/* Pipeline stages for test run */}
              <div style={{ marginBottom: 16 }}>
                {[
                  { label: 'Slide Rendering', icon: <Video size={13} />, step: 1 },
                  { label: 'Audio Synthesis (edge-tts)', icon: <Terminal size={13} />, step: 2 },
                  { label: 'Video Composition (FFmpeg)', icon: <Play size={13} />, step: 3 },
                  { label: 'Thumbnail', icon: <CheckCircle2 size={13} />, step: 4 },
                ].map(({ label, icon, step }) => {
                  const isDone = activeRun.status === 'done'
                  const isFailed = activeRun.status === 'failed'
                  const isActive = activeRun.status === 'running'
                  const stateClass = isDone ? 'done' : isFailed ? 'pending' : isActive ? 'active' : 'pending'
                  return (
                    <div key={step} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
                      <div className={`pipe-dot ${stateClass}`} style={{ width: 28, height: 28, fontSize: 11 }}>
                        {isDone ? '✓' : isActive ? '⋯' : step}
                      </div>
                      <span style={{ fontSize: 13, color: isDone ? 'var(--text)' : 'var(--text-muted)' }}>
                        {icon} {label}
                      </span>
                    </div>
                  )
                })}
              </div>

              {activeRun.status === 'done' && activeRun.video_path && (
                <div style={{ background: 'rgba(0,200,150,0.06)', border: '1px solid rgba(0,200,150,0.2)', borderRadius: 8, padding: '12px 16px' }}>
                  <div style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 600, marginBottom: 4 }}>✓ Video ready</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', wordBreak: 'break-all' }}>{activeRun.video_path}</div>
                </div>
              )}
              {activeRun.status === 'failed' && (
                <div style={{ background: 'rgba(255,95,95,0.06)', border: '1px solid rgba(255,95,95,0.2)', borderRadius: 8, padding: '12px 16px' }}>
                  <div style={{ fontSize: 12, color: 'var(--red)', fontWeight: 600, marginBottom: 4 }}>✗ Failed</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{activeRun.error}</div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Run history */}
      {allRuns && allRuns.length > 0 && (
        <div className="card">
          <div className="card-title">Run History</div>
          <table className="lesson-table">
            <thead><tr><th>Run ID</th><th>Fixture</th><th>Status</th><th>Started</th><th>Completed</th><th>Video</th></tr></thead>
            <tbody>
              {[...allRuns].reverse().map(r => (
                <tr key={r.id} onClick={() => setActiveRunId(r.id)} style={{ cursor: 'pointer' }}>
                  <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{r.id}</td>
                  <td style={{ color: 'var(--text-muted)', fontSize: 12 }}>{r.fixture?.split(/[\\/]/).pop()}</td>
                  <td><StatusBadge status={r.status} /></td>
                  <td style={{ color: 'var(--text-muted)', fontSize: 12 }}>{r.started_at?.slice(11, 19)}</td>
                  <td style={{ color: 'var(--text-muted)', fontSize: 12 }}>{r.completed_at?.slice(11, 19) || '—'}</td>
                  <td style={{ fontSize: 11, color: r.video_path ? 'var(--accent)' : 'var(--text-muted)' }}>
                    {r.video_path ? '✓ Ready' : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── App Shell ─────────────────────────────────────────────────────

function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="brand">theTwoCubes</div>
        <div className="sub">Video Automation v2</div>
      </div>
      <nav className="sidebar-nav">
        <NavLink to="/" end className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <LayoutDashboard size={16} /> Dashboard
        </NavLink>
        <NavLink to="/courses" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <BookOpen size={16} /> Courses
        </NavLink>
        <NavLink to="/test" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <FlaskConical size={16} /> Test Runner
        </NavLink>
        <NavLink to="/cost" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <DollarSign size={16} /> Cost Report
        </NavLink>
      </nav>
      <div className="sidebar-footer">API: localhost:8000</div>
    </aside>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <Sidebar />
        <div className="main">
          <Routes>
            <Route path="/" element={<><div className="topbar"><div className="topbar-title">Dashboard</div></div><div className="content"><Dashboard /></div></>} />
            <Route path="/courses" element={<><div className="topbar"><div className="topbar-title">Courses</div></div><div className="content"><Dashboard /></div></>} />
            <Route path="/courses/:courseId" element={<><div className="topbar"><div className="topbar-title">Course Detail</div></div><div className="content"><CoursePage /></div></>} />
            <Route path="/lessons/:lessonId" element={<><div className="topbar"><div className="topbar-title">Lesson Detail</div></div><div className="content"><LessonPage /></div></>} />
            <Route path="/test" element={<><div className="topbar"><div className="topbar-title">Test Runner</div></div><div className="content"><TestPage /></div></>} />
            <Route path="/cost" element={<><div className="topbar"><div className="topbar-title">Cost Report</div></div><div className="content"><CostPage /></div></>} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  )
}
