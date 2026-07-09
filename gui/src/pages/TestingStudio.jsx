import { useState, useEffect, useRef, useCallback } from 'react';

const API = 'http://localhost:8000';

/* ── tiny helpers ── */
const cx = (...args) => args.filter(Boolean).join(' ');

function useAPI(url, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  useEffect(() => {
    setLoading(true);
    fetch(API + url)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, deps);
  return { data, loading, error };
}

/* ── sub-components ── */

function SectionTitle({ children }) {
  return (
    <div className="text-xs font-bold text-emerald-400 uppercase tracking-widest mb-3">
      {children}
    </div>
  );
}

function Badge({ children, color = 'zinc' }) {
  const colors = {
    zinc: 'bg-zinc-800 text-zinc-300',
    emerald: 'bg-emerald-900/50 text-emerald-400',
    red: 'bg-red-900/50 text-red-400',
    amber: 'bg-amber-900/50 text-amber-400',
  };
  return (
    <span className={cx('text-xs px-2 py-0.5 rounded font-medium', colors[color])}>
      {children}
    </span>
  );
}

function LogPanel({ lines, status }) {
  const bottomRef = useRef(null);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [lines]);

  const statusColor = status === 'done' ? 'text-emerald-400' : status === 'error' ? 'text-red-400' : 'text-amber-400';

  return (
    <div className="bg-zinc-950 border border-zinc-800 rounded-lg overflow-hidden">
      <div className={cx('flex items-center gap-2 px-4 py-2 border-b border-zinc-800 text-xs font-mono', statusColor)}>
        <span className={cx('w-2 h-2 rounded-full', status === 'running' ? 'bg-amber-400 animate-pulse' : status === 'done' ? 'bg-emerald-400' : 'bg-red-400')} />
        {status || 'idle'}
      </div>
      <div className="h-56 overflow-y-auto p-4 font-mono text-xs text-zinc-300 space-y-0.5">
        {lines.length === 0 && <div className="text-zinc-600 italic">No output yet...</div>}
        {lines.map((line, i) => (
          <div key={i} className={cx(
            line.includes('Error') || line.includes('failed') ? 'text-red-400' :
            line.includes('Done') || line.includes('saved') || line.includes('success') ? 'text-emerald-400' :
            'text-zinc-300'
          )}>{line || ' '}</div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

function SlideGallery({ lessonId }) {
  const { data: slides, loading } = useAPI(`/api/lessons/${lessonId}/slides`, [lessonId]);
  const [selected, setSelected] = useState(0);

  if (loading) return <div className="text-zinc-500 text-sm py-4">Loading slides...</div>;
  if (!slides?.length) return <div className="text-zinc-500 text-sm py-4">No slides found</div>;

  return (
    <div className="space-y-4">
      {/* main preview */}
      <div className="border border-zinc-800 rounded-lg overflow-hidden bg-zinc-950">
        <img
          src={`${API}/static/${slides[selected]}`}
          alt={`Slide ${selected + 1}`}
          className="w-full"
          onError={e => { e.target.style.display = 'none'; }}
        />
      </div>
      {/* strip */}
      <div className="flex gap-2 overflow-x-auto pb-2">
        {slides.map((s, i) => (
          <button
            key={i}
            onClick={() => setSelected(i)}
            className={cx(
              'flex-shrink-0 w-24 h-14 rounded border-2 overflow-hidden transition-all',
              i === selected ? 'border-emerald-500' : 'border-zinc-800 hover:border-zinc-600'
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
      <div className="text-xs text-zinc-500">{selected + 1} / {slides.length} slides</div>
    </div>
  );
}

function VoiceSelector({ value, onChange }) {
  const { data: voices } = useAPI('/api/voices');
  const [previewing, setPreviewing] = useState(false);

  async function handlePreview() {
    if (!value) return;
    setPreviewing(true);
    try {
      const res = await fetch(`${API}/api/voices/preview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ voice: value }),
      });
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.play();
      audio.onended = () => URL.revokeObjectURL(url);
    } catch (e) {
      console.error(e);
    } finally {
      setPreviewing(false);
    }
  }

  return (
    <div className="space-y-2">
      <SectionTitle>Voice</SectionTitle>
      <div className="flex gap-2">
        <select
          value={value}
          onChange={e => onChange(e.target.value)}
          className="flex-1 bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-emerald-500"
        >
          <option value="">Use profile default</option>
          {(voices || []).map(v => (
            <option key={v.id} value={v.id}>{v.name} — {v.description}</option>
          ))}
        </select>
        <button
          onClick={handlePreview}
          disabled={!value || previewing}
          className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 disabled:opacity-40 text-zinc-200 text-sm rounded border border-zinc-700 transition-colors"
        >
          {previewing ? '▶ ...' : '▶ Preview'}
        </button>
      </div>
    </div>
  );
}

function ProfileSelector({ value, onChange }) {
  const { data: profiles } = useAPI('/api/profiles');

  return (
    <div className="space-y-2">
      <SectionTitle>Render Profile</SectionTitle>
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-emerald-500"
      >
        {(profiles || []).map(p => (
          <option key={p.name} value={p.name}>{p.name} — {p.description}</option>
        ))}
      </select>
    </div>
  );
}

/* ── Main Page ── */

export function TestingStudio() {
  const { data: lessons, loading: lessonsLoading } = useAPI('/api/lessons/rendered');

  // selections
  const [selectedLesson, setSelectedLesson] = useState(null);
  const [profile, setProfile] = useState('testing');
  const [voice, setVoice] = useState('');
  const [steps, setSteps] = useState({ slides: false, voice: false, video: false });
  const allSelected = steps.slides && steps.voice && steps.video;

  // rerender state
  const [taskId, setTaskId] = useState(null);
  const [logLines, setLogLines] = useState([]);
  const [taskStatus, setTaskStatus] = useState(null);
  const [running, setRunning] = useState(false);

  // live log via polling
  useEffect(() => {
    if (!taskId) return;
    let cancelled = false;
    let sent = 0;

    async function poll() {
      while (!cancelled) {
        try {
          const res = await fetch(`${API}/api/rerender/${taskId}`);
          const data = await res.json();
          const newLines = data.log || [];
          if (newLines.length > sent) {
            setLogLines(newLines);
            sent = newLines.length;
          }
          setTaskStatus(data.status);
          if (data.status === 'done' || data.status === 'error') {
            setRunning(false);
            break;
          }
        } catch (e) { /* ignore */ }
        await new Promise(r => setTimeout(r, 800));
      }
    }
    poll();
    return () => { cancelled = true; };
  }, [taskId]);

  function toggleStep(s) {
    setSteps(prev => ({ ...prev, [s]: !prev[s] }));
  }

  function toggleAll() {
    const next = !allSelected;
    setSteps({ slides: next, voice: next, video: next });
  }

  async function handleRun() {
    if (!selectedLesson) return;
    const stepsStr = allSelected ? 'all' : Object.entries(steps).filter(([, v]) => v).map(([k]) => k).join(',') || 'all';
    setRunning(true);
    setLogLines([]);
    setTaskStatus('running');
    setTaskId(null);
    try {
      const res = await fetch(`${API}/api/rerender`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          lesson_id: selectedLesson.lesson_id,
          steps: stepsStr,
          profile,
          voice,
          music: '',
        }),
      });
      const data = await res.json();
      setTaskId(data.task_id);
    } catch (e) {
      setLogLines([`Error: ${e.message}`]);
      setTaskStatus('error');
      setRunning(false);
    }
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-200 flex flex-col">
      {/* Header */}
      <div className="px-8 pt-8 pb-6 border-b border-zinc-900">
        <div className="flex items-center gap-3 mb-1">
          <div className="w-2 h-2 rounded-full bg-emerald-400" />
          <h1 className="text-2xl font-bold tracking-tight text-white">Testing Studio</h1>
        </div>
        <p className="text-zinc-500 text-sm ml-5">Re-render any lesson from checkpoints — no LLM calls, instant iteration.</p>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Left panel — controls */}
        <div className="w-96 flex-shrink-0 border-r border-zinc-900 overflow-y-auto p-6 space-y-8">

          {/* Lesson picker */}
          <div>
            <SectionTitle>Lesson</SectionTitle>
            {lessonsLoading ? (
              <div className="text-zinc-500 text-sm">Loading lessons...</div>
            ) : (
              <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                {(lessons || []).map(l => (
                  <button
                    key={l.lesson_id}
                    onClick={() => setSelectedLesson(l)}
                    className={cx(
                      'w-full text-left px-4 py-3 rounded-lg border text-sm transition-all',
                      selectedLesson?.lesson_id === l.lesson_id
                        ? 'border-emerald-500 bg-emerald-900/20 text-white'
                        : 'border-zinc-800 bg-zinc-900 text-zinc-300 hover:border-zinc-600'
                    )}
                  >
                    <div className="font-medium truncate">{l.title}</div>
                    <div className="flex gap-2 mt-1">
                      <Badge>{l.course_dir}</Badge>
                      {l.has_video && <Badge color="emerald">Has Video</Badge>}
                    </div>
                  </button>
                ))}
                {!lessonsLoading && !lessons?.length && (
                  <div className="text-zinc-500 text-sm italic">No rendered lessons found. Run the pipeline first.</div>
                )}
              </div>
            )}
          </div>

          {/* Profile */}
          <ProfileSelector value={profile} onChange={setProfile} />

          {/* Voice */}
          <VoiceSelector value={voice} onChange={setVoice} />

          {/* Steps */}
          <div>
            <SectionTitle>Steps to Re-run</SectionTitle>
            <div className="space-y-2">
              {/* All toggle */}
              <label className="flex items-center gap-3 px-3 py-2 rounded-lg bg-zinc-900 border border-zinc-700 cursor-pointer hover:border-emerald-600 transition-colors">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={toggleAll}
                  className="accent-emerald-500"
                />
                <span className="text-sm font-medium text-white">All Steps</span>
              </label>
              <div className="pl-4 space-y-1">
                {[
                  { key: 'slides', label: '🖼  Re-render Slides', hint: 'Applies new template to existing slide data' },
                  { key: 'voice', label: '🎙  Re-synthesize Voice', hint: 'Uses selected voice with existing script' },
                  { key: 'video', label: '🎬  Re-compose Video', hint: 'Rebuilds final MP4 with new profile settings' },
                ].map(({ key, label, hint }) => (
                  <label key={key} className="flex items-start gap-3 px-3 py-2.5 rounded-lg bg-zinc-900/50 border border-zinc-800 cursor-pointer hover:border-zinc-600 transition-colors">
                    <input
                      type="checkbox"
                      checked={steps[key]}
                      onChange={() => toggleStep(key)}
                      className="accent-emerald-500 mt-0.5"
                    />
                    <div>
                      <div className="text-sm text-zinc-200">{label}</div>
                      <div className="text-xs text-zinc-500 mt-0.5">{hint}</div>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          </div>

          {/* Run button */}
          <button
            onClick={handleRun}
            disabled={!selectedLesson || running || (!steps.slides && !steps.voice && !steps.video)}
            className={cx(
              'w-full py-3 rounded-lg text-sm font-bold transition-all',
              running
                ? 'bg-amber-800/50 text-amber-400 border border-amber-700 cursor-not-allowed'
                : !selectedLesson
                ? 'bg-zinc-800 text-zinc-500 border border-zinc-700 cursor-not-allowed'
                : 'bg-emerald-600 hover:bg-emerald-500 text-white border border-emerald-500 shadow-lg shadow-emerald-900/30'
            )}
          >
            {running ? '⏳ Running...' : '▶ Run Re-render'}
          </button>

          {/* Status badge */}
          {taskStatus && (
            <div className={cx(
              'text-center text-xs font-medium py-2 px-4 rounded-lg border',
              taskStatus === 'done' ? 'bg-emerald-900/30 text-emerald-400 border-emerald-800' :
              taskStatus === 'error' ? 'bg-red-900/30 text-red-400 border-red-800' :
              'bg-amber-900/30 text-amber-400 border-amber-800'
            )}>
              {taskStatus === 'done' ? '✓ Completed successfully' :
               taskStatus === 'error' ? '✗ Finished with errors' :
               '⏳ Running...'}
            </div>
          )}
        </div>

        {/* Right panel — output */}
        <div className="flex-1 overflow-y-auto p-6 space-y-8">
          {!selectedLesson ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="text-6xl mb-4">🎬</div>
              <div className="text-zinc-400 text-lg font-medium">Select a lesson to get started</div>
              <div className="text-zinc-600 text-sm mt-2">Choose a lesson from the left panel to re-render slides, voice, or video.</div>
            </div>
          ) : (
            <>
              {/* Lesson info */}
              <div className="border border-zinc-800 rounded-lg p-4 bg-zinc-900/50">
                <div className="text-white font-semibold">{selectedLesson.title}</div>
                <div className="flex gap-2 mt-2">
                  <Badge>{selectedLesson.course_dir}</Badge>
                  <Badge color="zinc">{selectedLesson.lesson_id.slice(0, 8)}</Badge>
                  {selectedLesson.checkpoints.map(cp => (
                    <Badge key={cp} color="emerald">{cp.replace('_', ' ')}</Badge>
                  ))}
                </div>
              </div>

              {/* Log output */}
              {(logLines.length > 0 || taskStatus) && (
                <div>
                  <SectionTitle>Output Log</SectionTitle>
                  <LogPanel lines={logLines} status={taskStatus} />
                </div>
              )}

              {/* Slide gallery — shown after render or if lesson has slides */}
              <div>
                <SectionTitle>Slide Gallery</SectionTitle>
                <SlideGallery key={selectedLesson.lesson_id + taskStatus} lessonId={selectedLesson.lesson_id} />
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
