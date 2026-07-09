import { useState, useEffect } from 'react';
import { Video, Terminal, Play, CheckCircle2, XCircle, Clock, Loader2 } from 'lucide-react';
import { useFetch } from '../hooks/useFetch';

const API = 'http://localhost:8000/api';

export function PipelineMonitor() {
  const [selectedCourse, setSelectedCourse] = useState('');
  const { data: courses } = useFetch(`${API}/courses`);
  const { data: lessons, refresh: refreshLessons } = useFetch(selectedCourse ? `${API}/courses/${selectedCourse}/lessons` : null);
  
  const [activeLessonId, setActiveLessonId] = useState(null);
  const [logs, setLogs] = useState([]);
  
  useEffect(() => {
    if (!activeLessonId) {
      setLogs([]);
      return;
    }
    
    setLogs([]);
    const es = new EventSource(`${API}/logs/lessons/${activeLessonId}`);
    
    es.onmessage = (event) => {
      setLogs(prev => [...prev, event.data].slice(-300)); // keep last 300 lines
      if (event.data.includes("Pipeline finished")) {
        refreshLessons();
      }
    };
    
    es.onerror = () => {
      es.close();
    };

    return () => es.close();
  }, [activeLessonId]);

  const handleStartGeneration = async (lesson) => {
    if (lesson.status === 'done' || lesson.status === 'failed') {
      if (!window.confirm(`Warning: Lesson "${lesson.title}" is currently marked as ${lesson.status.toUpperCase()}.\n\nGenerating it again will overwrite the existing video and files.\n\nAre you sure you want to proceed?`)) {
        return;
      }
    }

    try {
      setActiveLessonId(lesson.id);
      await fetch(`${API}/lessons/${lesson.id}/generate`, { method: 'POST' });
      // Poll a few times to refresh status
      setTimeout(refreshLessons, 1000);
      setTimeout(refreshLessons, 5000);
    } catch (e) {
      alert("Failed to start generation");
    }
  };

  const getStatusIcon = (status) => {
    switch(status) {
      case 'done': return <CheckCircle2 className="w-4 h-4 text-green-500" />;
      case 'failed': return <XCircle className="w-4 h-4 text-red-500" />;
      case 'pending': return <Clock className="w-4 h-4 text-zinc-500" />;
      default: return <Loader2 className="w-4 h-4 text-yellow-500 animate-spin" />;
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto h-screen flex flex-col">
      <header className="flex items-center gap-3 mb-8 shrink-0">
        <Video className="w-6 h-6 text-zinc-400" />
        <h1 className="text-2xl font-semibold tracking-tight">Pipeline Monitor</h1>
      </header>

      <div className="flex items-center gap-4 mb-6 shrink-0">
        <select value={selectedCourse} onChange={e => { setSelectedCourse(e.target.value); setActiveLessonId(null); }} className="w-full max-w-sm bg-zinc-900 border border-zinc-800 rounded-md px-3 py-2 text-white focus:outline-none focus:border-zinc-500">
          <option value="">-- Select a Course to Manage --</option>
          {courses?.map(c => (
            <option key={c.id} value={c.id}>{c.title}</option>
          ))}
        </select>
      </div>

      {!selectedCourse ? (
        <div className="flex-1 flex items-center justify-center border border-dashed border-zinc-800 rounded-xl text-zinc-500">
          Select a course from the dropdown above to view and manage its lessons.
        </div>
      ) : (
        <div className="flex flex-col lg:flex-row gap-6 flex-1 min-h-0">
          
          {/* Left Column: Lesson Selector */}
          <div className="flex flex-col w-full lg:w-1/2 shrink-0 border border-zinc-800 rounded-xl overflow-hidden bg-zinc-900/30">
            <div className="bg-zinc-900/80 border-b border-zinc-800 px-4 py-3 flex items-center justify-between shrink-0">
              <span className="text-sm font-medium text-zinc-300">Course Lessons</span>
              <span className="text-xs text-zinc-500">{lessons?.lessons?.length || 0} Total</span>
            </div>
            <div className="flex-1 overflow-y-auto p-2 space-y-1">
              {!lessons ? (
                <div className="p-4 text-center text-sm text-zinc-500">Loading lessons...</div>
              ) : !lessons.lessons || lessons.lessons.length === 0 ? (
                <div className="p-4 text-center text-sm text-zinc-500">No lessons found. Generate a curriculum first.</div>
              ) : (
                lessons.lessons.map(lesson => (
                  <div key={lesson.id} className={`flex items-center justify-between p-3 rounded-lg border transition-colors ${activeLessonId === lesson.id ? 'bg-zinc-800/80 border-zinc-600' : 'bg-zinc-950/50 border-zinc-800/50 hover:border-zinc-700'}`}>
                    <div className="flex items-center gap-3 min-w-0">
                      {getStatusIcon(lesson.status)}
                      <div className="flex flex-col min-w-0">
                        <span className="text-sm font-medium text-zinc-200 truncate">{lesson.position}. {lesson.title}</span>
                        <span className="text-xs text-zinc-500 font-mono">Status: {lesson.status}</span>
                      </div>
                    </div>
                    <button onClick={() => handleStartGeneration(lesson)} className="flex items-center gap-2 bg-white text-black text-xs font-medium px-3 py-1.5 rounded hover:bg-zinc-200 transition-colors shrink-0 ml-4">
                      <Play className="w-3 h-3" /> Generate
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Right Column: Live Logs */}
          <div className="flex-1 bg-zinc-950 border border-zinc-800 rounded-xl overflow-hidden flex flex-col min-w-0">
            <div className="bg-zinc-900/80 border-b border-zinc-800 px-4 py-3 flex items-center gap-2 shrink-0">
              <Terminal className="w-4 h-4 text-zinc-400" />
              <span className="text-sm font-mono text-zinc-300">
                Live Logs {activeLessonId ? `(Lesson ID: ${activeLessonId.slice(0, 8)}...)` : ''}
              </span>
            </div>
            <div className="flex-1 overflow-y-auto p-4 bg-black font-mono text-[11px] sm:text-xs leading-relaxed text-green-500 whitespace-pre-wrap break-all">
              {!activeLessonId ? (
                <div className="text-zinc-600">Select a lesson and click "Generate" to stream production logs.</div>
              ) : logs.length === 0 ? (
                <div className="text-zinc-600">Waiting for logs...</div>
              ) : (
                logs.map((log, i) => <div key={i}>{log}</div>)
              )}
            </div>
          </div>

        </div>
      )}
    </div>
  );
}
