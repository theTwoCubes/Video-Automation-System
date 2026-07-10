import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useFetch, usePolling } from '../hooks/useFetch';

const API = 'http://localhost:8000/api';
const cx = (...a) => a.filter(Boolean).join(' ');

const S = {
  label: 'text-[10px] font-bold text-teal-400 uppercase tracking-[0.15em] mb-1.5 block',
  card:  'bg-[#0d0d0d] border border-[#1a1a1a] rounded-xl',
  input: 'w-full bg-[#111] border border-[#222] rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-teal-500 transition-colors',
};

function StatusTag({ status }) {
  const map = {
    ready:   'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20',
    running: 'bg-amber-500/10 text-amber-400 border border-amber-500/20 animate-pulse',
    done:    'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20',
    failed:  'bg-red-500/10 text-red-400 border border-red-500/20',
    pending: 'bg-zinc-800 text-zinc-500 border border-zinc-700',
  };
  return (
    <span className={cx('inline-block text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wide', map[status] || 'bg-zinc-800 text-zinc-500')}>
      {status}
    </span>
  );
}

export function Curricula() {
  const { courseId } = useParams();
  const { data: courses, refresh: refreshCourses } = useFetch(`${API}/courses`);
  const course = courses?.find(c => c.id === courseId || c.course_id === courseId);

  const [tab, setTab]           = useState('knowledge');
  const [sourceFile, setFile]   = useState(null);
  const [sourceName, setName]   = useState('');
  const [minLessons, setMin]    = useState(15);

  const [ingestTaskId, setIngestId] = useState(null);
  const ingestStatus = usePolling(ingestTaskId ? `${API}/ingest/${ingestTaskId}` : null, 2000, !!ingestTaskId);

  const [currTaskId, setCurrId] = useState(null);
  const currStatus = usePolling(currTaskId ? `${API}/curricula/tasks/${currTaskId}` : null, 2000, !!currTaskId);

  // Section browser
  const { data: sectionsData } = useFetch(course?.source ? `${API}/courses/${courseId}/sections` : null);
  const [selSec,     setSelSec]     = useState(null);
  const [secText,    setSecText]    = useState('');
  const [secLoading, setSecLoading] = useState(false);

  useEffect(() => {
    if (ingestStatus?.status === 'done' || ingestStatus?.status === 'failed') refreshCourses();
  }, [ingestStatus?.status, refreshCourses]);

  useEffect(() => {
    if (currStatus?.status === 'done' || currStatus?.status === 'failed') refreshCourses();
  }, [currStatus?.status, refreshCourses]);

  if (!course && courses) return (
    <div className="p-8 text-zinc-500 text-sm">Course not found. <Link to="/" className="text-teal-400 underline">Back to Dashboard</Link></div>
  );
  if (!course) return (
    <div className="p-8 text-zinc-700 text-sm">Loading...</div>
  );

  async function handleUpload(e) {
    e.preventDefault();
    if (!sourceFile) return;
    const fd = new FormData();
    fd.append('name', sourceName || sourceFile.name);
    fd.append('file', sourceFile);
    try {
      const res  = await fetch(`${API}/courses/${courseId}/source`, { method: 'POST', body: fd });
      const data = await res.json();
      if (data.task_id) { setIngestId(data.task_id); refreshCourses(); }
    } catch { alert('Failed to start PDF processing'); }
  }

  async function handleSectionClick(sectionId) {
    setSelSec(sectionId); setSecLoading(true); setSecText('');
    try {
      const res = await fetch(`${API}/courses/${courseId}/sections/${sectionId}`);
      if (res.ok) { const d = await res.json(); setSecText(d.text || ''); }
    } catch { setSecText('Failed to load section text.'); }
    setSecLoading(false);
  }

  async function handleGenerate() {
    try {
      const res  = await fetch(`${API}/curricula/generate`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ course_id: courseId, min_lessons: Number(minLessons) }),
      });
      const data = await res.json();
      if (data.task_id) setCurrId(data.task_id);
    } catch { alert('Failed to start generation'); }
  }

  const sections  = sectionsData?.sections || [];
  const topLevel  = sections.filter(s => !s.id.includes('.'));
  const children  = pid => sections.filter(s => {
    const p = s.id.split('.');
    return p.length === pid.split('.').length + 1 && s.id.startsWith(pid + '.');
  });

  const TABS = [
    { id: 'knowledge',  label: 'Knowledge Base' },
    { id: 'curriculum', label: 'Curriculum'      },
  ];

  return (
    <div className="min-h-screen bg-black text-zinc-200 flex flex-col" style={{ fontFamily: "'Inter', sans-serif" }}>

      {// Header}
      <div className="px-8 pt-7 pb-5 border-b border-[#111]">
        <Link to="/" className="text-[11px] text-zinc-600 hover:text-teal-400 transition-colors flex items-center gap-1 mb-3 w-fit">
          ← Back to Dashboard
        </Link>
        <div className="flex items-end gap-3">
          <div className="w-1.5 h-5 bg-teal-400 rounded-full" />
          <h1 className="text-xl font-bold text-white tracking-tight">{course.title}</h1>
          {course.source?.status && <StatusTag status={course.source.status} />}
        </div>
        <p className="text-zinc-600 text-[13px] ml-4 mt-1">{course.topic || course.course_id}</p>
      </div>

      {// Tabs}
      <div className="flex gap-1 px-8 pt-4 border-b border-[#111]">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={cx(
              'px-4 py-2 text-[13px] font-medium rounded-t-lg border border-b-0 transition-colors',
              tab === t.id
                ? 'border-[#1e1e1e] bg-[#0d0d0d] text-white'
                : 'border-transparent text-zinc-600 hover:text-zinc-300'
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {// Body}
      <div className="flex-1 p-8 overflow-y-auto">

        {// KNOWLEDGE BASE TAB}
        {tab === 'knowledge' && (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-8 h-full">

            {// Left: Active PDF + Upload}
            <div className="space-y-5">

              {// Active source}
              {course.source && (
                <div className={cx(S.card, 'p-4 flex items-start gap-4')}>
                  <div className="w-10 h-10 bg-[#111] border border-[#1e1e1e] rounded-lg flex items-center justify-center text-xl flex-shrink-0">
                    📄
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[13px] font-semibold text-white truncate">{course.source.name}</div>
                    <div className="text-[11px] text-zinc-600 mt-0.5">
                      {course.source.section_count} sections indexed
                    </div>
                  </div>
                  <StatusTag status={course.source.status} />
                </div>
              )}

              {// Upload form}
              <div className={cx(S.card, 'p-5')}>
                <div className="text-[13px] font-semibold text-white mb-1">
                  {course.source ? '↑ Replace Course PDF' : '↑ Upload Course PDF'}
                </div>
                <p className="text-[11px] text-zinc-600 mb-4">One PDF per course. Must follow the structured LaTeX format.</p>

                <form onSubmit={handleUpload} className="space-y-4">
                  {// Drop zone}
                  <label className={cx(
                    'flex flex-col items-center justify-center w-full h-28 border-2 border-dashed rounded-xl cursor-pointer transition-all',
                    sourceFile ? 'border-teal-500/40 bg-teal-500/5' : 'border-[#222] hover:border-[#333]'
                  )}>
                    <input type="file" accept=".pdf" className="hidden"
                      onChange={e => { setFile(e.target.files[0]); if (!sourceName) setName(e.target.files[0]?.name || ''); }} />
                    {sourceFile ? (
                      <div className="text-center">
                        <div className="text-2xl mb-1">📄</div>
                        <div className="text-[12px] text-zinc-300 font-medium">{sourceFile.name}</div>
                        <div className="text-[10px] text-zinc-600 mt-0.5">{(sourceFile.size / 1024 / 1024).toFixed(1)} MB</div>
                      </div>
                    ) : (
                      <div className="text-center text-zinc-600">
                        <div className="text-2xl mb-1">↑</div>
                        <div className="text-[12px]">Drop PDF or click to browse</div>
                      </div>
                    )}
                  </label>

                  {// Name input}
                  <div>
                    <span className={S.label}>Display Name</span>
                    <input className={S.input} placeholder="e.g. C++ Complete Guide v2"
                      value={sourceName} onChange={e => setName(e.target.value)} />
                  </div>

                  <button type="submit" disabled={!sourceFile || ingestStatus?.status === 'running'}
                    className="w-full py-2.5 rounded-xl text-[13px] font-bold bg-teal-500 hover:bg-teal-400 text-black transition-colors disabled:opacity-40">
                    {ingestStatus?.status === 'running' ? '⏳ Processing PDF...' : 'Process PDF'}
                  </button>

                  {ingestStatus && (
                    <div className={cx(S.card, 'px-4 py-3 text-[12px]')}>
                      <span className="text-zinc-600">Status: </span>
                      <StatusTag status={ingestStatus.status} />
                      {ingestStatus.status === 'done' && (
                        <span className="text-zinc-500 ml-2">- {ingestStatus.section_count} sections indexed</span>
                      )}
                      {ingestStatus.error && (
                        <div className="text-red-400 mt-1.5">{ingestStatus.error}</div>
                      )}
                    </div>
                  )}
                </form>
              </div>
            </div>

            {// Right: Section browser}
            <div className={cx(S.card, 'flex flex-col overflow-hidden', 'min-h-[400px]')}>
              <div className="px-5 py-3.5 border-b border-[#1a1a1a] flex items-center justify-between flex-shrink-0">
                <span className="text-[13px] font-semibold text-white">Section Browser</span>
                {sectionsData && (
                  <span className="text-[10px] text-zinc-600">{sectionsData.section_count} sections</span>
                )}
              </div>

              {!course.source ? (
                <div className="flex-1 flex items-center justify-center text-zinc-700 text-[13px] italic p-8 text-center">
                  Upload a PDF to browse its sections here.
                </div>
              ) : !sectionsData ? (
                <div className="flex-1 flex items-center justify-center text-zinc-700 text-[13px]">
                  Loading sections...
                </div>
              ) : (
                <div className="flex flex-1 overflow-hidden">
                  {// Tree}
                  <div className="w-1/2 overflow-y-auto border-r border-[#1a1a1a] p-2 space-y-px">
                    {topLevel.map(ch => (
                      <div key={ch.id}>
                        <button onClick={() => handleSectionClick(ch.id)}
                          className={cx(
                            'w-full text-left px-2.5 py-1.5 rounded-lg text-[12px] font-medium flex items-center gap-2 transition-colors',
                            selSec === ch.id ? 'bg-teal-500/10 text-teal-300' : 'text-zinc-400 hover:text-zinc-200 hover:bg-[#111]'
                          )}>
                          <span className="text-zinc-700 font-mono text-[10px] flex-shrink-0">{ch.id}</span>
                          <span className="truncate">{ch.title}</span>
                        </button>
                        {children(ch.id).map(sec => (
                          <div key={sec.id}>
                            <button onClick={() => handleSectionClick(sec.id)}
                              className={cx(
                                'w-full text-left px-2.5 py-1 pl-5 rounded-lg text-[11px] flex items-center gap-2 transition-colors',
                                selSec === sec.id ? 'bg-teal-500/10 text-teal-400' : 'text-zinc-500 hover:text-zinc-300 hover:bg-[#111]'
                              )}>
                              <span className="text-zinc-700 font-mono text-[10px] flex-shrink-0">{sec.id}</span>
                              <span className="truncate">{sec.title}</span>
                            </button>
                            {children(sec.id).map(sub => (
                              <button key={sub.id} onClick={() => handleSectionClick(sub.id)}
                                className={cx(
                                  'w-full text-left px-2.5 py-1 pl-8 rounded-lg text-[10px] flex items-center gap-2 transition-colors',
                                  selSec === sub.id ? 'bg-teal-500/10 text-teal-400' : 'text-zinc-600 hover:text-zinc-400 hover:bg-[#111]'
                                )}>
                                <span className="text-zinc-700 font-mono flex-shrink-0">{sub.id}</span>
                                <span className="truncate">{sub.title}</span>
                              </button>
                            ))}
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>

                  {// Text preview}
                  <div className="w-1/2 overflow-y-auto p-4">
                    {!selSec && (
                      <div className="text-zinc-700 text-[12px] mt-4 text-center italic">
                        Click a section to preview
                      </div>
                    )}
                    {secLoading && <div className="text-zinc-600 text-[12px] animate-pulse">Loading...</div>}
                    {!secLoading && secText && (
                      <pre className="text-[11px] text-zinc-400 whitespace-pre-wrap leading-relaxed font-mono">
                        {secText}
                      </pre>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {// CURRICULUM TAB}
        {tab === 'curriculum' && (
          <div className="max-w-3xl space-y-5">

            {!course.source && (
              <div className="p-4 bg-amber-500/5 border border-amber-500/20 rounded-xl text-amber-300 text-[13px] flex items-start gap-3">
                <span className="mt-0.5 flex-shrink-0">⚠</span>
                <span>Upload and process a PDF in <button onClick={() => setTab('knowledge')} className="underline underline-offset-2 hover:text-amber-200">Knowledge Base</button> before generating a curriculum.</span>
              </div>
            )}

            <div className={cx(S.card, 'p-5')}>
              <div className="flex items-center justify-between gap-4 flex-wrap">
                <div>
                  <div className="text-[13px] font-semibold text-white mb-0.5">Generate Curriculum</div>
                  <div className="text-[11px] text-zinc-600">AI will plan lectures from the PDF table of contents.</div>
                </div>
                <div className="flex items-center gap-3">
                  <div>
                    <span className={S.label}>Target Lessons</span>
                    <input type="number" min="1" value={minLessons} onChange={e => setMin(e.target.value)}
                      className={cx(S.input, 'w-24 text-center')} />
                  </div>
                  <div className="pt-5">
                    <button onClick={handleGenerate}
                      disabled={!course.source || currStatus?.status === 'running'}
                      className="px-5 py-2.5 rounded-xl text-[13px] font-bold bg-teal-500 hover:bg-teal-400 text-black transition-colors disabled:opacity-40 flex items-center gap-2">
                      {currStatus?.status === 'running' ? '⏳ Generating...' : '▶ Generate'}
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {currStatus?.status === 'running' && (
              <div className={cx(S.card, 'px-5 py-8 text-center text-zinc-500 text-[13px] animate-pulse')}>
                LLM is planning lectures from the table of contents…
              </div>
            )}

            {currStatus?.error && (
              <div className="p-4 bg-red-500/5 border border-red-500/20 rounded-xl text-red-300 text-[13px]">
                {currStatus.error}
              </div>
            )}

            {currStatus?.status === 'done' && currStatus.lecture_count && (
              <div className="text-[13px] text-emerald-400 font-medium flex items-center gap-2">
                <span>✓</span>
                {currStatus.lecture_count} lectures planned and created in DB
              </div>
            )}

            {// Output JSON}
            {(!currStatus || currStatus.status === 'done') && (
              <div className={cx(S.card, 'overflow-hidden')}>
                <div className="px-4 py-2.5 border-b border-[#1a1a1a] flex items-center gap-2 bg-[#0a0a0a]">
                  <span className="w-2 h-2 rounded-full bg-[#222]" />
                  <span className="text-[10px] font-mono text-zinc-600">curriculum.json</span>
                </div>
                <div className="p-4 overflow-x-auto max-h-96">
                  <pre className="text-[11px] text-zinc-400 font-mono leading-relaxed">
                    {currStatus?.curriculum
                      ? JSON.stringify(currStatus.curriculum, null, 2)
                      : 'No curriculum generated yet.'}
                  </pre>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
