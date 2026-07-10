import { useState, useEffect, useRef } from 'react';

const API = 'http://localhost:8000';
const cx = (...a) => a.filter(Boolean).join(' ');

// Data hook
function useAPI(url, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    setLoading(true); setError(null);
    fetch(API + url)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return { data, loading, error };
}

// Design tokens
const S = {
  label: 'text-[10px] font-bold text-teal-400 uppercase tracking-[0.15em] mb-1.5 block',
  card:  'bg-[#0d0d0d] border border-[#1a1a1a] rounded-xl',
  input: 'w-full bg-[#111] border border-[#222] rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-teal-500 transition-colors',
  pill:  'inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full',
};

// Status pill
function StatusPill({ status }) {
  if (!status) return null;
  const map = {
    done:    ['bg-emerald-500/10 text-emerald-400 border border-emerald-500/30', '✓ Done'],
    error:   ['bg-red-500/10 text-red-400 border border-red-500/30', '✗ Error'],
    running: ['bg-amber-500/10 text-amber-400 border border-amber-500/30 animate-pulse', '● Running'],
  };
  const [cls, label] = map[status] || ['bg-zinc-800 text-zinc-400 border border-zinc-700', status];
  return <span className={cx(S.pill, cls)}>{label}</span>;
}

// Checkpoint badge
function CkBadge({ name }) {
  const colors = {
    lesson_planner: 'bg-violet-500/10 text-violet-400',
    write_script:   'bg-blue-500/10 text-blue-400',
    generate_slides:'bg-teal-500/10 text-teal-400',
    synthesize_voice:'bg-pink-500/10 text-pink-400',
    compose_video:  'bg-orange-500/10 text-orange-400',
  };
  return (
    <span className={cx(S.pill, colors[name] || 'bg-zinc-800 text-zinc-400')}>
      {name.replace(/_/g, ' ')}
    </span>
  );
}

// Log panel
function LogPanel({ lines, status }) {
  const ref = useRef(null);
  const containerRef = useRef(null);
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 100;
    if (isNearBottom) ref.current?.scrollIntoView({ behavior: 'smooth' });
  }, [lines]);

  return (
    <div className={cx(S.card, 'overflow-hidden flex flex-col')}>
      {/* title bar */}
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-[#1a1a1a] bg-[#0a0a0a]">
        <span className={cx(
          'w-2 h-2 rounded-full',
          status === 'running' ? 'bg-amber-400 animate-pulse' :
          status === 'done'    ? 'bg-emerald-400' :
          status === 'error'   ? 'bg-red-400' : 'bg-zinc-600'
        )} />
        <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider">
          {status || 'idle'}
        </span>
      </div>
      {/* log body */}
      <div ref={containerRef} className="h-52 overflow-y-auto p-3 font-mono text-[11px] leading-relaxed space-y-px">
        {lines.length === 0 && (
          <div className="text-zinc-700 italic mt-4 text-center">No output yet...</div>
        )}
        {lines.map((line, i) => (
          <div key={i} className={
            line.includes('Error') || line.includes('failed') || line.includes('Traceback')
              ? 'text-red-400'
              : line.includes('Done') || line.includes('success') || line.includes('saved')
              ? 'text-emerald-400'
              : line.startsWith('[')
              ? 'text-teal-400'
              : 'text-zinc-400'
          }>{line || '\u00a0'}</div>
        ))}
        <div ref={ref} />
      </div>
    </div>
  );
}

// Slide gallery
function SlideGallery({ lessonId, refreshKey }) {
  const { data: slides, loading } = useAPI(
    `/api/lessons/${lessonId}/slides`,
    [lessonId, refreshKey]
  );
  const [sel, setSel] = useState(0);

  useEffect(() => { setSel(0); }, [lessonId, refreshKey]);

  if (loading) return (
    <div className="flex items-center justify-center h-40 text-zinc-600 text-sm">
      Loading slides...
    </div>
  );
  if (!slides?.length) return (
    <div className="flex items-center justify-center h-40 text-zinc-700 text-sm italic">
      No slides found
    </div>
  );

  return (
    <div className="space-y-3">
      {/* main preview */}
      <div className={cx(S.card, 'overflow-hidden relative group')}>
        <img
          src={`${API}/static/${slides[sel]}`}
          alt={`Slide ${sel + 1}`}
          className="w-full block"
          onError={e => { e.target.alt = 'Image unavailable'; }}
        />
        <div className="absolute bottom-2 right-3 bg-black/60 text-zinc-400 text-[10px] font-mono px-2 py-1 rounded">
          {sel + 1} / {slides.length}
        </div>
      </div>
      {/* thumbnail strip */}
      <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-thin">
        {slides.map((s, i) => (
          <button
            key={i}
            onClick={() => setSel(i)}
            className={cx(
              'flex-shrink-0 w-20 h-12 rounded-lg overflow-hidden border-2 transition-all duration-150',
              i === sel
                ? 'border-teal-500 ring-1 ring-teal-500/30'
                : 'border-[#222] hover:border-[#444]'
            )}
          >
            <img
              src={`${API}/static/${s}`}
              alt={`Slide ${i + 1}`}
              className="w-full h-full object-cover"
            />
          </button>
        ))}
      </div>
    </div>
  );
}

// Lesson list item
function LessonItem({ lesson, selected, onClick }) {
  return (
    <button
      onClick={onClick}
      className={cx(
        'w-full text-left px-3 py-3 rounded-xl border transition-all duration-150 group',
        selected
          ? 'border-teal-500/60 bg-teal-500/5 text-white'
          : 'border-[#1c1c1c] bg-[#0a0a0a] text-zinc-400 hover:border-[#2a2a2a] hover:text-zinc-200'
      )}
    >
      <div className="font-medium text-[13px] truncate">{lesson.title}</div>
      <div className="flex flex-wrap gap-1.5 mt-2">
        <span className="text-[10px] text-zinc-600">{lesson.course_dir}</span>

        {lesson.has_video && (
          <span className={cx(S.pill, 'bg-orange-500/10 text-orange-400')}>🎬 video</span>
        )}
      </div>
    </button>
  );
}

// Main Page
export function TestingStudio() {
  const { data: lessons, loading: lessonsLoading } = useAPI('/api/lessons/rendered');
  const { data: profiles } = useAPI('/api/profiles');
  const { data: voices }   = useAPI('/api/voices');

  const [query,    setQuery]    = useState('');
  const [lesson,   setLesson]   = useState(null);
  const [profile,  setProfile]  = useState('testing');
  const [voice,    setVoice]    = useState('');
  const [steps,    setSteps]    = useState({ slides: false, voice: false, video: false });
  const [running,  setRunning]  = useState(false);
  const [taskId,   setTaskId]   = useState(null);
  const [logLines, setLogLines] = useState([]);
  const [status,   setStatus]   = useState(null);
  const [refreshGallery, setRefreshGallery] = useState(0);
  const [previewing, setPreviewing] = useState(false);

  const allSteps = steps.slides && steps.voice && steps.video;
  const anyStep  = steps.slides || steps.voice || steps.video;

  const filtered = (lessons || []).filter(l =>
    !query || l.title?.toLowerCase().includes(query.toLowerCase())
  );

  // live log polling
  useEffect(() => {
    if (!taskId) return;
    let cancelled = false;
    let sent = 0;
    (async function poll() {
      while (!cancelled) {
        try {
          const res  = await fetch(`${API}/api/rerender/${taskId}`);
          const data = await res.json();
          if ((data.log || []).length > sent) {
            setLogLines(data.log);
            sent = data.log.length;
          }
          setStatus(data.status);
          if (data.status === 'done' || data.status === 'error') {
            setRunning(false);
            if (data.status === 'done') setRefreshGallery(k => k + 1);
            break;
          }
        } catch {/* ignore */}
        await new Promise(r => setTimeout(r, 800));
      }
    })();
    return () => { cancelled = true; };
  }, [taskId]);

  function toggleStep(k) { setSteps(p => ({ ...p, [k]: !p[k] })); }
  function toggleAll()   { const n = !allSteps; setSteps({ slides: n, voice: n, video: n }); }

  async function handleRun() {
    if (!lesson) return;
    const stepsStr = allSteps ? 'all'
      : Object.entries(steps).filter(([, v]) => v).map(([k]) => k).join(',') || 'all';
    setRunning(true); setLogLines([]); setStatus('running'); setTaskId(null);
    try {
      const res  = await fetch(`${API}/api/rerender`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lesson_id: lesson.lesson_id, steps: stepsStr, profile, voice, music: '' }),
      });
      const data = await res.json();
      setTaskId(data.task_id);
    } catch (e) {
      setLogLines([`Error: ${e.message}`]); setStatus('error'); setRunning(false);
    }
  }

  async function handlePreviewVoice() {
    if (!voice || previewing) return;
    setPreviewing(true);
    try {
      const res  = await fetch(`${API}/api/voices/preview`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ voice }),
      });
      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = new Audio(url);
      a.play();
      a.onended = () => URL.revokeObjectURL(url);
    } catch {/* ignore */} finally { setPreviewing(false); }
  }

  return (
    <div className="min-h-screen bg-black text-zinc-200 flex flex-col" style={{ fontFamily: "'Inter', sans-serif" }}>

      {/* Page Header */}
      <div className="px-8 pt-7 pb-5 border-b border-[#111] flex items-end justify-between">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <div className="w-1.5 h-5 bg-teal-400 rounded-full" />
            <h1 className="text-xl font-bold text-white tracking-tight">Testing Studio</h1>
          </div>
          <p className="text-zinc-600 text-[13px] ml-4">
            Re-render slides, voice, or video from checkpoints - no LLM calls.
          </p>
        </div>
        {status && <StatusPill status={status} />}
      </div>

      {/* 3-column body */}
      <div className="flex flex-1 overflow-hidden">

        {/* COL 1: Lesson Picker */}
        <div className="w-72 flex-shrink-0 border-r border-[#111] flex flex-col">
          <div className="p-4 border-b border-[#111]">
            <span className={S.label}>Lessons</span>
            <input
              type="search"
              placeholder="Search lessons..."
              value={query}
              onChange={e => setQuery(e.target.value)}
              className={S.input}
            />
          </div>
          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {lessonsLoading && (
              <div className="text-zinc-700 text-[13px] text-center mt-8">Loading...</div>
            )}
            {!lessonsLoading && !filtered.length && (
              <div className="text-zinc-700 text-[13px] italic text-center mt-8">
                {query ? 'No results' : 'No rendered lessons found'}
              </div>
            )}
            {filtered.map(l => (
              <LessonItem
                key={l.lesson_id}
                lesson={l}
                selected={lesson?.lesson_id === l.lesson_id}
                onClick={() => setLesson(l)}
              />
            ))}
          </div>
        </div>

        {/* COL 2: Settings Panel */}
        <div className="w-72 flex-shrink-0 border-r border-[#111] overflow-y-auto p-5 space-y-6">

          {/* Profile */}
          <div>
            <span className={S.label}>Render Profile</span>
            <select value={profile} onChange={e => setProfile(e.target.value)} className={S.input}>
              {(profiles || []).map(p => (
                <option key={p.name} value={p.name}>{p.name}{p.description ? ` - ${p.description}` : ''}</option>
              ))}
            </select>
          </div>

          {/* Voice */}
          <div>
            <span className={S.label}>Voice</span>
            <div className="flex gap-2">
              <select value={voice} onChange={e => setVoice(e.target.value)} className={cx(S.input, 'flex-1')}>
                <option value="">Profile default</option>
                {(voices || []).map(v => (
                  <option key={v.id} value={v.id}>{v.name}</option>
                ))}
              </select>
              <button
                onClick={handlePreviewVoice}
                disabled={!voice || previewing}
                className="flex-shrink-0 px-3 py-2 bg-[#111] border border-[#222] rounded-lg text-zinc-400 hover:text-zinc-200 hover:border-[#333] transition-all disabled:opacity-30 text-sm"
                title="Preview voice"
              >
                {previewing ? '...' : '▶'}
              </button>
            </div>
          </div>

          {/* Steps */}
          <div>
            <span className={S.label}>Steps to Re-run</span>
            <div className="space-y-2">
              <label className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-[#0d0d0d] border border-[#1e1e1e] cursor-pointer hover:border-teal-500/30 transition-colors">
                <input type="checkbox" checked={allSteps} onChange={toggleAll}
                  className="accent-teal-500 w-3.5 h-3.5" />
                <span className="text-[13px] font-semibold text-zinc-200">All Steps</span>
              </label>
              {[
                { key: 'slides', icon: '🖼', label: 'Re-render Slides',   hint: 'New template, same data' },
                { key: 'voice',  icon: '🎙', label: 'Re-synthesize Voice', hint: 'Selected voice + existing script' },
                { key: 'video',  icon: '🎬', label: 'Re-compose Video',   hint: 'Rebuild final MP4' },
              ].map(({ key, icon, label, hint }) => (
                <label key={key}
                  className="flex items-start gap-3 px-3 py-2.5 rounded-lg bg-[#080808] border border-[#161616] cursor-pointer hover:border-[#2a2a2a] transition-colors ml-2"
                >
                  <input type="checkbox" checked={steps[key]} onChange={() => toggleStep(key)}
                    className="accent-teal-500 w-3.5 h-3.5 mt-0.5" />
                  <div>
                    <div className="text-[13px] text-zinc-300">{icon}  {label}</div>
                    <div className="text-[11px] text-zinc-600 mt-0.5">{hint}</div>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Run button */}
          <button
            onClick={handleRun}
            disabled={!lesson || running || !anyStep}
            className={cx(
              'w-full py-3 rounded-xl text-[13px] font-bold tracking-wide transition-all duration-200',
              running
                ? 'bg-amber-900/30 text-amber-400 border border-amber-700/50 cursor-not-allowed'
                : !lesson || !anyStep
                ? 'bg-[#0d0d0d] text-zinc-600 border border-[#1a1a1a] cursor-not-allowed'
                : 'bg-teal-500 hover:bg-teal-400 text-black border border-teal-400 shadow-lg shadow-teal-900/30 active:scale-[0.98]'
            )}
          >
            {running ? '⏳  Running...' : '▶  Run Re-render'}
          </button>

          {/* Selected lesson summary */}
          {lesson && (
            <div className={cx(S.card, 'p-3 space-y-1.5')}>
              <span className={S.label}>Selected</span>
              <div className="text-[13px] text-white font-medium leading-snug">{lesson.title}</div>
              <div className="text-[10px] text-zinc-600 font-mono">{lesson.lesson_id}</div>
            </div>
          )}
        </div>

        {/* COL 3: Output - Gallery + Logs */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {!lesson ? (
            <div className="flex flex-col items-center justify-center h-full gap-4 text-center">
              <div className="w-16 h-16 rounded-2xl bg-[#0d0d0d] border border-[#1a1a1a] flex items-center justify-center text-3xl">
                🎬
              </div>
              <div>
                <div className="text-zinc-300 font-semibold">No lesson selected</div>
                <div className="text-zinc-600 text-sm mt-1">
                  Choose a lesson from the left panel to begin
                </div>
              </div>
            </div>
          ) : (
            <>
              {/* Lesson info bar */}
              <div className={cx(S.card, 'px-4 py-3 flex items-center justify-between gap-4')}>
                <div>
                  <div className="text-[13px] font-semibold text-white">{lesson.title}</div>

                </div>
                <StatusPill status={status} />
              </div>

              {/* Slide gallery */}
              <div>
                <span className={S.label}>Slide Gallery</span>
                <SlideGallery
                  key={`${lesson.lesson_id}-${refreshGallery}`}
                  lessonId={lesson.lesson_id}
                  refreshKey={refreshGallery}
                />
              </div>

              {/* Logs */}
              {(logLines.length > 0 || status) && (
                <div>
                  <span className={S.label}>Output Log</span>
                  <LogPanel lines={logLines} status={status} />
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
