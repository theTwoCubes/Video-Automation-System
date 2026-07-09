import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { FlaskConical, Play, Upload, BookOpen, AlertTriangle, ChevronRight, FileText } from 'lucide-react';
import { useFetch, usePolling } from '../hooks/useFetch';

const API = 'http://localhost:8000/api';

export function Curricula() {
  const { courseId } = useParams();
  const { data: courses, refresh: refreshCourses } = useFetch(`${API}/courses`);
  const course = courses?.find(c => c.id === courseId);

  const [activeTab, setActiveTab] = useState('knowledge');
  const [sourceFile, setSourceFile] = useState(null);
  const [sourceName, setSourceName] = useState('');

  const [ingestTaskId, setIngestTaskId] = useState(null);
  const ingestStatus = usePolling(ingestTaskId ? `${API}/ingest/${ingestTaskId}` : null, 2000, !!ingestTaskId);

  const [currTaskId, setCurrTaskId] = useState(null);
  const currStatus = usePolling(currTaskId ? `${API}/curricula/tasks/${currTaskId}` : null, 2000, !!currTaskId);

  useEffect(() => {
    if (ingestStatus?.status === 'done' || ingestStatus?.status === 'failed') {
      refreshCourses();
    }
  }, [ingestStatus?.status]);

  useEffect(() => {
    if (currStatus?.status === 'done' || currStatus?.status === 'failed') {
      refreshCourses();
    }
  }, [currStatus?.status]);

  const [minLessons, setMinLessons] = useState(15);

  // Section browser
  const { data: sectionsData } = useFetch(
    course?.source ? `${API}/courses/${courseId}/sections` : null
  );
  const [selectedSectionId, setSelectedSectionId] = useState(null);
  const [sectionText, setSectionText] = useState('');
  const [sectionLoading, setSectionLoading] = useState(false);

  if (!course && courses) return <div className="p-8 text-zinc-400">Course not found.</div>;
  if (!course) return <div className="p-8 text-zinc-400">Loading...</div>;

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!sourceFile) return;
    try {
      const formData = new FormData();
      formData.append('name', sourceName || sourceFile.name);
      formData.append('file', sourceFile);

      const res = await fetch(`${API}/courses/${courseId}/source`, {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (data.task_id) {
        setIngestTaskId(data.task_id);
        refreshCourses();
      }
    } catch (e) {
      alert("Failed to start PDF processing");
    }
  };

  const handleSectionClick = async (sectionId) => {
    setSelectedSectionId(sectionId);
    setSectionLoading(true);
    setSectionText('');
    try {
      const res = await fetch(`${API}/courses/${courseId}/sections/${sectionId}`);
      if (res.ok) {
        const data = await res.json();
        setSectionText(data.text || '');
      }
    } catch (err) {
      setSectionText('Failed to load section text.');
    }
    setSectionLoading(false);
  };

  const handleGenerate = async () => {
    try {
      const res = await fetch(`${API}/curricula/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ course_id: courseId, min_lessons: Number(minLessons) }),
      });
      const data = await res.json();
      if (data.task_id) setCurrTaskId(data.task_id);
    } catch (e) {
      alert("Failed to start generation");
    }
  };

  const sections = sectionsData?.sections || [];
  const topLevel = sections.filter(s => !s.id.includes('.'));
  const getChildren = (parentId) => sections.filter(s => {
    const parts = s.id.split('.');
    return parts.length === parentId.split('.').length + 1 && s.id.startsWith(parentId + '.');
  });

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <header className="flex items-center gap-4 mb-8">
        <Link to="/" className="text-zinc-500 hover:text-white transition-colors">← Back</Link>
        <div className="flex items-center gap-3">
          <FlaskConical className="w-6 h-6 text-zinc-400" />
          <h1 className="text-2xl font-semibold tracking-tight">{course.title}</h1>
        </div>
      </header>

      <div className="flex gap-4 border-b border-zinc-800 mb-6">
        <button onClick={() => setActiveTab('knowledge')} className={`pb-3 px-2 text-sm font-medium transition-colors ${activeTab === 'knowledge' ? 'border-b-2 border-white text-white' : 'text-zinc-400 hover:text-zinc-200'}`}>Knowledge Base</button>
        <button onClick={() => setActiveTab('curriculum')} className={`pb-3 px-2 text-sm font-medium transition-colors ${activeTab === 'curriculum' ? 'border-b-2 border-white text-white' : 'text-zinc-400 hover:text-zinc-200'}`}>Curriculum</button>
      </div>

      {activeTab === 'knowledge' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Left — upload + source info */}
          <div className="space-y-6">
            {/* Active source card */}
            {course.source && (
              <div className="bg-zinc-900/50 border border-zinc-700 p-5 rounded-xl">
                <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">Active PDF</h2>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-zinc-100 font-medium">{course.source.name}</span>
                  <span className={`text-xs px-2 py-0.5 rounded uppercase font-mono ${course.source.status === 'ready' ? 'text-green-400 bg-green-900/30' : 'text-yellow-400 bg-yellow-900/30'}`}>
                    {course.source.status}
                  </span>
                </div>
                <div className="text-xs text-zinc-500">
                  {course.source.section_count} sections parsed
                </div>
              </div>
            )}

            {/* Upload form */}
            <div className="bg-zinc-900/30 border border-zinc-800 p-6 rounded-xl">
              <h2 className="text-lg font-medium mb-1 flex items-center gap-2">
                <Upload className="w-5 h-5 text-zinc-400" />
                {course.source ? 'Replace PDF' : 'Upload Course PDF'}
              </h2>
              <p className="text-xs text-zinc-500 mb-4">One PDF per course. Must follow the structured LaTeX format.</p>
              <form onSubmit={handleUpload} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-zinc-400 mb-1.5">PDF File</label>
                  <label className={`flex flex-col items-center justify-center w-full h-28 border-2 border-dashed rounded-lg cursor-pointer transition-colors ${sourceFile ? 'border-zinc-500 bg-zinc-900/40' : 'border-zinc-700 hover:border-zinc-500'}`}>
                    <input type="file" accept=".pdf" className="hidden" onChange={e => { setSourceFile(e.target.files[0]); if (!sourceName) setSourceName(e.target.files[0]?.name || ''); }} />
                    {sourceFile ? (
                      <div className="text-center">
                        <FileText className="w-6 h-6 text-zinc-400 mx-auto mb-1" />
                        <span className="text-sm text-zinc-300">{sourceFile.name}</span>
                        <span className="block text-xs text-zinc-500">{(sourceFile.size / 1024 / 1024).toFixed(1)} MB</span>
                      </div>
                    ) : (
                      <div className="text-center text-zinc-500 text-sm">
                        <Upload className="w-5 h-5 mx-auto mb-1" />
                        Drop PDF here or click
                      </div>
                    )}
                  </label>
                </div>
                <div>
                  <label className="block text-sm font-medium text-zinc-400 mb-1.5">Name</label>
                  <input value={sourceName} onChange={e => setSourceName(e.target.value)} className="w-full bg-zinc-900 border border-zinc-800 rounded-md px-3 py-2 text-white focus:border-zinc-500 focus:outline-none" placeholder="e.g. C++ Complete Guide" />
                </div>
                <button type="submit" disabled={!sourceFile || ingestStatus?.status === 'running'} className="w-full bg-white text-black font-medium py-2 rounded-md hover:bg-zinc-200 disabled:opacity-50 transition-colors">
                  {ingestStatus?.status === 'running' ? 'Processing...' : 'Process PDF'}
                </button>
                {ingestStatus && (
                  <div className="mt-2 p-3 bg-zinc-900 rounded-md text-sm">
                    Status: <span className={`font-medium ${ingestStatus.status === 'done' ? 'text-green-400' : ingestStatus.status === 'failed' ? 'text-red-400' : 'text-yellow-400'}`}>{ingestStatus.status}</span>
                    {ingestStatus.status === 'done' && <span className="text-zinc-500 ml-2">— {ingestStatus.section_count} sections indexed</span>}
                    {ingestStatus.error && <div className="text-red-400 mt-1 text-xs">{ingestStatus.error}</div>}
                  </div>
                )}
              </form>
            </div>
          </div>

          {/* Right — Section Browser */}
          <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl flex flex-col overflow-hidden">
            <div className="p-5 border-b border-zinc-800">
              <h2 className="text-sm font-semibold text-zinc-300 flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-zinc-400" />
                Section Browser
                {sectionsData && <span className="ml-auto text-xs text-zinc-500 font-normal">{sectionsData.section_count} sections</span>}
              </h2>
            </div>
            {!course.source ? (
              <div className="flex-1 flex items-center justify-center p-8 text-zinc-500 text-sm text-center">
                Upload a PDF to browse its sections here.
              </div>
            ) : !sectionsData ? (
              <div className="flex-1 flex items-center justify-center p-8 text-zinc-500 text-sm">Loading sections...</div>
            ) : (
              <div className="flex flex-1 overflow-hidden">
                {/* Section tree */}
                <div className="w-1/2 overflow-y-auto border-r border-zinc-800 p-3 space-y-0.5">
                  {topLevel.map(chapter => (
                    <div key={chapter.id}>
                      <button
                        onClick={() => handleSectionClick(chapter.id)}
                        className={`w-full text-left px-2 py-1.5 rounded text-sm font-medium flex items-center gap-1 transition-colors ${selectedSectionId === chapter.id ? 'bg-zinc-700 text-white' : 'text-zinc-300 hover:bg-zinc-800'}`}
                      >
                        <ChevronRight className="w-3 h-3 text-zinc-500 flex-shrink-0" />
                        <span className="text-zinc-500 font-mono text-xs mr-1">{chapter.id}</span>
                        <span className="truncate">{chapter.title}</span>
                      </button>
                      {getChildren(chapter.id).map(sec => (
                        <div key={sec.id}>
                          <button
                            onClick={() => handleSectionClick(sec.id)}
                            className={`w-full text-left px-2 py-1 pl-5 rounded text-xs flex items-center gap-1 transition-colors ${selectedSectionId === sec.id ? 'bg-zinc-700 text-white' : 'text-zinc-400 hover:bg-zinc-800'}`}
                          >
                            <span className="text-zinc-600 font-mono mr-1">{sec.id}</span>
                            <span className="truncate">{sec.title}</span>
                          </button>
                          {getChildren(sec.id).map(sub => (
                            <button
                              key={sub.id}
                              onClick={() => handleSectionClick(sub.id)}
                              className={`w-full text-left px-2 py-1 pl-9 rounded text-xs flex items-center gap-1 transition-colors ${selectedSectionId === sub.id ? 'bg-zinc-700 text-white' : 'text-zinc-500 hover:bg-zinc-800'}`}
                            >
                              <span className="text-zinc-600 font-mono mr-1">{sub.id}</span>
                              <span className="truncate">{sub.title}</span>
                            </button>
                          ))}
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
                {/* Section text preview */}
                <div className="w-1/2 overflow-y-auto p-4">
                  {!selectedSectionId && <div className="text-zinc-600 text-xs">Click a section to preview its content.</div>}
                  {sectionLoading && <div className="text-zinc-500 text-xs animate-pulse">Loading...</div>}
                  {!sectionLoading && sectionText && (
                    <pre className="text-xs text-zinc-300 whitespace-pre-wrap leading-relaxed font-mono">{sectionText}</pre>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'curriculum' && (
        <div className="bg-zinc-900/30 border border-zinc-800 p-6 rounded-xl">
          {!course.source && (
            <div className="mb-6 p-4 bg-yellow-950/30 border border-yellow-800/40 rounded-lg text-yellow-200 text-sm flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              You must upload and process a PDF in the Knowledge Base tab before generating a curriculum.
            </div>
          )}
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-medium flex items-center gap-2"><BookOpen className="w-5 h-5 text-zinc-400" /> Curriculum</h2>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <label className="text-sm text-zinc-400">Target Lectures:</label>
                <input
                  type="number" min="1"
                  value={minLessons}
                  onChange={(e) => setMinLessons(e.target.value)}
                  className="w-20 bg-zinc-900 border border-zinc-800 rounded-md px-2 py-1 text-white focus:border-zinc-500 focus:outline-none"
                />
              </div>
              <button
                onClick={handleGenerate}
                disabled={!course.source || currStatus?.status === 'running'}
                className="flex items-center gap-2 bg-white text-black px-4 py-2 rounded-md font-medium hover:bg-zinc-200 disabled:opacity-50 transition-colors"
              >
                <Play className="w-4 h-4" /> Generate Curriculum
              </button>
            </div>
          </div>

          {currStatus?.status === 'running' && (
            <div className="p-8 text-center text-zinc-400 animate-pulse">LLM is planning lectures from the TOC...</div>
          )}
          {currStatus?.error && (
            <div className="p-4 bg-red-950/30 border border-red-900/50 rounded-lg text-red-200 mb-4">
              <AlertTriangle className="inline w-4 h-4 mr-2" /> {currStatus.error}
            </div>
          )}
          {(!currStatus || currStatus.status === 'done') && (
            <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-md font-mono text-sm text-zinc-300 overflow-x-auto max-h-[500px]">
              <pre>{currStatus?.curriculum ? JSON.stringify(currStatus.curriculum, null, 2) : 'No curriculum generated yet.'}</pre>
            </div>
          )}
          {currStatus?.status === 'done' && currStatus.lecture_count && (
            <div className="mt-4 text-sm text-green-400 font-medium">
              ✓ {currStatus.lecture_count} lectures planned. Lesson rows created in DB.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
