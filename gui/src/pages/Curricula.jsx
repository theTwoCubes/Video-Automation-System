import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { FlaskConical, Play, Search, Upload, BookOpen, AlertTriangle } from 'lucide-react';
import { useFetch, usePolling } from '../hooks/useFetch';

const API = 'http://localhost:8000/api';

export function Curricula() {
  const { courseId } = useParams();
  const { data: courses, refresh: refreshCourses } = useFetch(`${API}/courses`);
  const course = courses?.find(c => c.id === courseId);

  const [activeTab, setActiveTab] = useState('knowledge');
  const [sourceFile, setSourceFile] = useState(null);
  const [sourceUrl, setSourceUrl] = useState('');
  const [sourceName, setSourceName] = useState('');
  const [sourceType, setSourceType] = useState('url');
  
  const [query, setQuery] = useState('');
  const [queryResults, setQueryResults] = useState([]);
  const [queryLoading, setQueryLoading] = useState(false);

  const [ingestTaskId, setIngestTaskId] = useState(null);
  const ingestStatus = usePolling(ingestTaskId ? `${API}/ingest/${ingestTaskId}` : null, 2000, !!ingestTaskId);

  const [currTaskId, setCurrTaskId] = useState(null);
  const currStatus = usePolling(currTaskId ? `${API}/curricula/tasks/${currTaskId}` : null, 2000, !!currTaskId);

  if (!course && courses) return <div className="p-8 text-zinc-400">Course not found.</div>;
  if (!course) return <div className="p-8 text-zinc-400">Loading...</div>;

  const handleIngest = async (e) => {
    e.preventDefault();
    try {
      const formData = new FormData();
      formData.append('name', sourceName);
      formData.append('source_type', sourceType);
      
      if (sourceType === 'pdf' && sourceFile) {
        formData.append('file', sourceFile);
      } else {
        formData.append('source', sourceUrl);
      }

      const res = await fetch(`${API}/courses/${courseId}/source`, {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (data.task_id) setIngestTaskId(data.task_id);
    } catch (e) {
      alert("Failed to start ingestion");
    }
  };

  const handleQuery = async (e) => {
    e.preventDefault();
    setQueryLoading(true);
    try {
      const res = await fetch(`${API}/courses/${courseId}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      });
      if(res.ok) {
        const data = await res.json();
        setQueryResults(data.chunks || []);
      }
    } catch (err) {
      console.error(err);
    }
    setQueryLoading(false);
  };

  const handleGenerate = async () => {
    try {
      const res = await fetch(`${API}/curricula/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ course_id: courseId, min_lessons: 15 }),
      });
      const data = await res.json();
      if (data.task_id) setCurrTaskId(data.task_id);
    } catch (e) {
      alert("Failed to start generation");
    }
  };

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
          <div className="space-y-6">
            {course.source && (
              <div className="bg-zinc-900/50 border border-zinc-700 p-5 rounded-xl">
                <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-3">Active Knowledge Source</h2>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-zinc-100 font-medium">{course.source.name}</span>
                  <span className="text-xs bg-zinc-800 text-zinc-300 px-2 py-0.5 rounded uppercase">{course.source.type}</span>
                </div>
                <div className="flex items-center gap-4 text-xs text-zinc-500 mb-3">
                  <span>Chunks: {course.source.chunk_count}</span>
                  <span>Status: <span className={course.source.status === 'done' ? 'text-green-500' : 'text-yellow-500'}>{course.source.status}</span></span>
                </div>
                {course.source.topic_tags && course.source.topic_tags.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {course.source.topic_tags.map(tag => (
                      <span key={tag} className="px-2 py-1 bg-zinc-800/50 border border-zinc-700 text-zinc-300 text-[10px] uppercase tracking-wider rounded-md">
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div className="bg-zinc-900/30 border border-zinc-800 p-6 rounded-xl">
              <h2 className="text-lg font-medium mb-4 flex items-center gap-2">
                <Upload className="w-5 h-5 text-zinc-400" /> {course.source ? 'Overwrite Source' : 'Add Knowledge Source'}
              </h2>
              <form onSubmit={handleIngest} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-zinc-400 mb-1.5">Source Type</label>
                  <select className="w-full bg-zinc-900 border border-zinc-800 rounded-md px-3 py-2 text-white focus:border-zinc-500" value={sourceType} onChange={e => {setSourceType(e.target.value); setSourceFile(null); setSourceUrl('');}}>
                    <option value="url">URL</option>
                    <option value="pdf">PDF Upload</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-zinc-400 mb-1.5">{sourceType === 'pdf' ? 'Upload PDF' : 'URL'}</label>
                  {sourceType === 'pdf' ? (
                    <input required type="file" accept=".pdf" onChange={e => setSourceFile(e.target.files[0])} className="w-full bg-zinc-900 border border-zinc-800 rounded-md px-3 py-2 text-zinc-300 focus:border-zinc-500 file:mr-4 file:py-1 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-medium file:bg-zinc-800 file:text-zinc-300 hover:file:bg-zinc-700" />
                  ) : (
                    <input required value={sourceUrl} onChange={e => setSourceUrl(e.target.value)} className="w-full bg-zinc-900 border border-zinc-800 rounded-md px-3 py-2 text-white focus:border-zinc-500" placeholder="https://..." />
                  )}
                </div>
                <div>
                  <label className="block text-sm font-medium text-zinc-400 mb-1.5">Source Name</label>
                  <input required value={sourceName} onChange={e => setSourceName(e.target.value)} className="w-full bg-zinc-900 border border-zinc-800 rounded-md px-3 py-2 text-white focus:border-zinc-500" placeholder="e.g. Official Docs" />
                </div>
                <button type="submit" disabled={ingestStatus?.status === 'running'} className="w-full bg-white text-black font-medium py-2 rounded-md hover:bg-zinc-200 disabled:opacity-50 transition-colors">
                  {course.source ? 'Overwrite Data' : 'Ingest Data'}
                </button>
                
                {ingestStatus && (
                  <div className="mt-4 p-3 bg-zinc-900 rounded-md text-sm">
                    Status: <span className="font-medium text-yellow-500">{ingestStatus.status}</span>
                    {ingestStatus.error && <div className="text-red-400 mt-1">{ingestStatus.error}</div>}
                  </div>
                )}
              </form>
            </div>
          </div>

          <div className="bg-zinc-900/30 border border-zinc-800 p-6 rounded-xl">
            <h2 className="text-lg font-medium mb-4 flex items-center gap-2"><Search className="w-5 h-5 text-zinc-400" /> Test Retrieval</h2>
            <form onSubmit={handleQuery} className="flex gap-2 mb-4">
              <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Type a concept..." className="flex-1 bg-zinc-900 border border-zinc-800 rounded-md px-3 py-2 focus:border-zinc-500" />
              <button type="submit" disabled={queryLoading} className="px-4 bg-zinc-800 text-white rounded-md hover:bg-zinc-700 transition-colors">Test</button>
            </form>
            <div className="space-y-3 overflow-y-auto max-h-96 pr-2">
              {queryResults.map((res, i) => (
                <div key={i} className="p-3 bg-zinc-900 border border-zinc-800 rounded-md text-xs text-zinc-300 leading-relaxed">
                  {res}
                </div>
              ))}
              {queryResults.length === 0 && !queryLoading && (
                <div className="text-zinc-500 text-sm">No results yet. Ingest data and try querying.</div>
              )}
              {queryLoading && <div className="text-zinc-500 text-sm">Searching ChromaDB...</div>}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'curriculum' && (
        <div className="bg-zinc-900/30 border border-zinc-800 p-6 rounded-xl">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-medium flex items-center gap-2"><BookOpen className="w-5 h-5 text-zinc-400" /> Generated Curriculum</h2>
            <button onClick={handleGenerate} disabled={currStatus?.status === 'running'} className="flex items-center gap-2 bg-white text-black px-4 py-2 rounded-md font-medium hover:bg-zinc-200 disabled:opacity-50 transition-colors">
              <Play className="w-4 h-4" /> Generate AI Curriculum
            </button>
          </div>
          
          {currStatus && currStatus.status === 'running' && (
            <div className="p-8 text-center text-zinc-400 animate-pulse">AI is planning the curriculum...</div>
          )}

          {currStatus?.error && (
            <div className="p-4 bg-red-950/30 border border-red-900/50 rounded-lg text-red-200 mb-4">
              <AlertTriangle className="inline w-4 h-4 mr-2" /> {currStatus.error}
            </div>
          )}

          {(!currStatus || currStatus.status === 'done') && (
            <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-md font-mono text-sm text-zinc-300 overflow-x-auto">
              <pre>{currStatus?.curriculum ? JSON.stringify(currStatus.curriculum, null, 2) : 'No curriculum generated yet.'}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
