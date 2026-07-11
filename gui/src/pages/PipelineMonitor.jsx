import { useState, useEffect, useRef } from 'react';
import { useFetch, usePolling } from '../hooks/useFetch';
import { S, cx, STAGES, pipelineProgress } from '../lib/ui';

const API = 'http://localhost:8000/api';

function StatusPill({ status }) {
  if (!status) return null;
  const map = {
    done:    ['bg-emerald-500/10 text-emerald-400 border border-emerald-500/30', '✓ Done'],
    failed:  ['bg-red-500/10 text-red-400 border border-red-500/30', '✗ Failed'],
    running: ['bg-amber-500/10 text-amber-400 border border-amber-500/30 animate-pulse', '● Running'],
    pending: ['bg-[#111] text-zinc-500 border border-[#222]', '○ Pending'],
  };
  const [cls, label] = map[status] || ['bg-zinc-800 text-zinc-400 border border-zinc-700', status];
  return (
    <span className={cx('inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full whitespace-nowrap', cls)}>
      {label}
    </span>
  );
}

// Live production monitor: turns the raw log stream into an 11-stage progress
// strip (blueprint §14/§23), replacing coarse pending/processing/done status.
function StageStepper({ logs }) {
  const { index, done } = pipelineProgress(logs);
  return (
    <div className="px-4 py-2.5 border-b border-[#1a1a1a] bg-[#080808] flex flex-wrap gap-1.5 flex-shrink-0">
      {STAGES.map((s, i) => {
        const state = done || i < index ? 'done' : i === index ? 'active' : 'pending';
        return (
          <span key={s.key} className={cx(
            'text-[10px] font-mono px-2 py-1 rounded-md border whitespace-nowrap',
            state === 'done'   ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
            : state === 'active' ? 'bg-amber-500/10 text-amber-400 border-amber-500/30 animate-pulse'
            : 'bg-[#111] text-zinc-600 border-[#1e1e1e]'
          )}>
            {state === 'done' ? '✓ ' : state === 'active' ? '● ' : ''}{s.label}
          </span>
        );
      })}
    </div>
  );
}

export function PipelineMonitor() {
  const [selectedCourse, setSelectedCourse] = useState('');
  const { data: courses } = useFetch(`${API}/courses`);
  const lessonsData = usePolling(selectedCourse ? `${API}/courses/${selectedCourse}/lessons` : null, 3000);
  
  const [activeLessonId, setActiveLessonId] = useState(null);
  const [logs, setLogs] = useState([]);
  const logsContainerRef = useRef(null);
  const logsEndRef = useRef(null);

  useEffect(() => {
    if (!activeLessonId) { setLogs([]); return; }

    setLogs([]);
    const es = new EventSource(`${API}/logs/lessons/${activeLessonId}`);

    es.onmessage = (event) => {
      setLogs(prev => {
        const next = [...prev, event.data];
        return next.length > 500 ? next.slice(next.length - 500) : next;
      });
    };
    es.onerror = () => es.close();
    return () => es.close();
  }, [activeLessonId]);

  // Auto-scroll only when new logs arrive, and only if the user was already
  // near the bottom - so scrolling up to read earlier output isn't fought.
  useEffect(() => {
    const container = logsContainerRef.current;
    if (!container) return;
    const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 100;
    if (isNearBottom) {
      logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  const progress = pipelineProgress(logs);
  const running = activeLessonId && logs.length > 0 && !progress.done;

  async function handleStartGeneration(lesson) {
    if (lesson.status === 'done' || lesson.status === 'failed') {
      if (!window.confirm(`Warning: Lesson "${lesson.title}" is currently marked as ${lesson.status.toUpperCase()}.\n\nGenerating it again will overwrite the existing video and files.\n\nAre you sure you want to proceed?`)) {
        return;
      }
    }
    try {
      setActiveLessonId(lesson.id);
      await fetch(`${API}/lessons/${lesson.id}/generate`, { method: 'POST' });
    } catch { alert("Failed to start generation"); }
  }

  async function handleCancel() {
    if (!activeLessonId) return;
    if (!window.confirm('Stop the running generation for this lesson?')) return;
    try {
      const r = await fetch(`${API}/lessons/${activeLessonId}/cancel`, { method: 'POST' });
      if (!r.ok) alert('No running generation to cancel.');
    } catch { alert('Failed to cancel'); }
  }

  return (
    <div className="min-h-screen bg-black text-zinc-200 flex flex-col p-8" style={{ fontFamily: "'Inter', sans-serif" }}>
      
      {/* Header */}
      <div className="flex items-end justify-between mb-8 flex-shrink-0">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <div className="w-1.5 h-5 bg-teal-400 rounded-full" />
            <h1 className="text-xl font-bold text-white tracking-tight">Pipeline Monitor</h1>
          </div>
          <p className="text-zinc-600 text-[13px] ml-4">
            Manage course lessons and stream live production logs.
          </p>
        </div>
        <div className="w-80">
          <select 
            value={selectedCourse} 
            onChange={e => { setSelectedCourse(e.target.value); setActiveLessonId(null); }} 
            className={S.input}
          >
            <option value="">-- Select a Course --</option>
            {courses?.map(c => (
              <option key={c.id} value={c.id}>{c.title}</option>
            ))}
          </select>
        </div>
      </div>

      {!selectedCourse ? (
        <div className="flex-1 flex flex-col items-center justify-center border border-dashed border-[#222] rounded-2xl text-zinc-600 gap-3">
          <div className="text-3xl">⚙️</div>
          <div className="text-[13px] font-medium text-zinc-500">Select a course to view lessons</div>
        </div>
      ) : (
        <div className="flex flex-1 gap-6 min-h-0">
          
          {/* Left Column: Lessons */}
          <div className={cx(S.card, 'w-[45%] flex flex-col overflow-hidden min-h-0')}>
            <div className="px-5 py-3.5 border-b border-[#1a1a1a] flex items-center justify-between flex-shrink-0 bg-[#0a0a0a]">
              <span className="text-[13px] font-semibold text-white">Course Lessons</span>
              <span className="text-[10px] text-zinc-600">{lessonsData?.lessons?.length || 0} Total</span>
            </div>
            
            <div className="flex-1 overflow-y-auto p-3 space-y-1.5 bg-[#080808]">
              {!lessonsData ? (
                <div className="p-8 text-center text-[12px] text-zinc-600">Loading lessons...</div>
              ) : !lessonsData.lessons?.length ? (
                <div className="p-8 text-center text-[12px] text-zinc-600 italic">
                  No lessons found. Generate a curriculum first.
                </div>
              ) : (
                lessonsData.lessons.map(lesson => (
                  <div 
                    key={lesson.id} 
                    className={cx(
                      'flex items-center justify-between p-3 rounded-lg border transition-all duration-150',
                      activeLessonId === lesson.id 
                        ? 'bg-teal-500/10 border-teal-500/30' 
                        : 'bg-[#111] border-[#1e1e1e] hover:border-[#2a2a2a]'
                    )}
                  >
                    <div className="flex items-center gap-3 min-w-0 pr-4">
                      <div className="flex-shrink-0 w-6 text-center text-[11px] font-mono text-zinc-500">
                        {lesson.position}
                      </div>
                      <div className="flex flex-col min-w-0">
                        <span className={cx(
                          'text-[13px] font-medium truncate mb-1',
                          activeLessonId === lesson.id ? 'text-teal-400' : 'text-zinc-200'
                        )}>
                          {lesson.title}
                        </span>
                        <StatusPill status={lesson.status} />
                      </div>
                    </div>
                    <button 
                      onClick={() => handleStartGeneration(lesson)} 
                      className={cx(
                        'flex-shrink-0 flex items-center gap-2 text-[11px] font-bold px-3 py-2 rounded-md transition-all',
                        lesson.status === 'running'
                          ? 'bg-[#111] text-zinc-500 border border-[#222] cursor-not-allowed'
                          : 'bg-teal-500 hover:bg-teal-400 text-black shadow-sm active:scale-95'
                      )}
                      disabled={lesson.status === 'running'}
                    >
                      {lesson.status === 'running' ? '● Running' : '▶ Generate'}
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Right Column: Logs */}
          <div className={cx(S.card, 'flex-1 flex flex-col overflow-hidden min-h-0 relative')}>
            <div className="px-5 py-3.5 border-b border-[#1a1a1a] flex items-center gap-3 flex-shrink-0 bg-[#0a0a0a] z-10">
              <span className="w-2 h-2 rounded-full bg-[#333]" />
              <span className="text-[11px] font-mono text-zinc-400 uppercase tracking-wider">
                Live Output {activeLessonId ? `· ${activeLessonId.slice(0,8)}` : ''}
              </span>
              {running && (
                <button
                  onClick={handleCancel}
                  className="ml-auto text-[10px] font-bold px-2.5 py-1 rounded-md bg-red-500/10 text-red-400 border border-red-500/30 hover:bg-red-500/20 transition-colors"
                >
                  ■ Cancel
                </button>
              )}
            </div>

            {activeLessonId && <StageStepper logs={logs} />}

            <div ref={logsContainerRef} className="flex-1 overflow-y-auto p-5 bg-black font-mono text-[11px] leading-relaxed break-all">
              {!activeLessonId ? (
                <div className="text-zinc-700 italic h-full flex items-center justify-center">
                  Select a lesson to view logs
                </div>
              ) : logs.length === 0 ? (
                <div className="text-zinc-600 h-full flex items-center justify-center animate-pulse">
                  Waiting for connection...
                </div>
              ) : (
                <div className="space-y-px">
                  {logs.map((log, i) => (
                    <div key={i} className={cx(
                      log.includes('Error') || log.includes('failed') || log.includes('Traceback')
                        ? 'text-red-400'
                        : log.includes('Done') || log.includes('success')
                        ? 'text-emerald-400'
                        : log.startsWith('[')
                        ? 'text-teal-500/80'
                        : 'text-zinc-400'
                    )}>
                      {log || '\u00a0'}
                    </div>
                  ))}
                  {/* Anchor to scroll to bottom */}
                  <div style={{ float: "left", clear: "both" }} ref={logsEndRef}></div>
                </div>
              )}
            </div>
          </div>

        </div>
      )}
    </div>
  );
}
