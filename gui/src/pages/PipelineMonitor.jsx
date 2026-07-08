import { useState, useEffect } from 'react';
import { Video, Terminal, Play } from 'lucide-react';
import { useFetch } from '../hooks/useFetch';

const API = 'http://localhost:8000/api';

export function PipelineMonitor() {
  const [selectedCourse, setSelectedCourse] = useState('');
  const { data: courses } = useFetch(`${API}/courses`);
  const [logs, setLogs] = useState([]);
  
  useEffect(() => {
    if (!selectedCourse) {
      setLogs([]);
      return;
    }
    
    setLogs([]);
    const es = new EventSource(`${API}/logs/${selectedCourse}`);
    
    es.onmessage = (event) => {
      setLogs(prev => [...prev, event.data].slice(-100)); // keep last 100 lines
    };
    
    es.onerror = () => {
      es.close();
    };

    return () => es.close();
  }, [selectedCourse]);

  const handleStartGeneration = async () => {
    if (!selectedCourse) return;
    try {
      await fetch(`${API}/courses/${selectedCourse}/generate`, { method: 'POST' });
    } catch (e) {
      alert("Failed to start generation");
    }
  };

  return (
    <div className="p-8 max-w-6xl mx-auto h-screen flex flex-col">
      <header className="flex items-center gap-3 mb-8 shrink-0">
        <Video className="w-6 h-6 text-zinc-400" />
        <h1 className="text-2xl font-semibold tracking-tight">Pipeline Monitor</h1>
      </header>

      <div className="flex flex-col md:flex-row gap-6 flex-1 min-h-0">
        <div className="flex flex-col gap-6 w-full md:w-1/3 shrink-0">
          <div className="bg-zinc-900/30 border border-zinc-800 p-6 rounded-xl">
            <h2 className="text-lg font-medium mb-2">Run Production Generation</h2>
            <p className="text-sm text-zinc-400 mb-4">Start generating video assets for the next pending lesson.</p>
            <div className="flex flex-col gap-4">
              <select value={selectedCourse} onChange={e => setSelectedCourse(e.target.value)} className="w-full bg-zinc-950 border border-zinc-800 rounded-md px-3 py-2 focus:border-zinc-500">
                <option value="">-- Select a course --</option>
                {courses?.map(c => (
                  <option key={c.id} value={c.id}>{c.title}</option>
                ))}
              </select>
              <button disabled={!selectedCourse} onClick={handleStartGeneration} className="w-full flex items-center justify-center gap-2 bg-white text-black font-medium py-2 rounded-md hover:bg-zinc-200 disabled:opacity-50 transition-colors">
                <Play className="w-4 h-4" /> Run Next Lesson
              </button>
            </div>
          </div>

          <div className="bg-zinc-900/30 border border-zinc-800 p-6 rounded-xl">
            <h2 className="text-lg font-medium mb-2">Run Automated Test</h2>
            <p className="text-sm text-zinc-400 mb-4">Run the pipeline using cached LLM outputs from tests/fixtures to test rendering without spending API credits.</p>
            <button onClick={async () => {
              try {
                const res = await fetch(`${API}/test/run`, {
                  method: 'POST',
                  headers: {'Content-Type': 'application/json'},
                  body: JSON.stringify({ fixture_path: 'tests/fixtures/cpp_variables_lesson.json', force_restart: true, from_step: 'slides' })
                });
                const d = await res.json();
                if(d.run_id) alert('Test pipeline started! Check backend console for logs.');
              } catch(e) { alert('Failed to start test'); }
            }} className="w-full flex items-center justify-center gap-2 border border-zinc-700 text-zinc-300 font-medium py-2 rounded-md hover:bg-zinc-800 transition-colors">
              <Play className="w-4 h-4" /> Run Test (C++ Variables)
            </button>
          </div>
        </div>

        <div className="flex-1 bg-zinc-950 border border-zinc-800 rounded-xl overflow-hidden flex flex-col min-w-0">
          <div className="bg-zinc-900/50 border-b border-zinc-800 px-4 py-3 flex items-center gap-2 shrink-0">
            <Terminal className="w-4 h-4 text-zinc-400" />
            <span className="text-sm font-mono text-zinc-300">Live Logs {selectedCourse ? `(${selectedCourse})` : ''}</span>
          </div>
          <div className="flex-1 overflow-y-auto p-4 bg-black font-mono text-xs leading-relaxed text-green-500 whitespace-pre-wrap break-all">
            {!selectedCourse ? (
              <div className="text-zinc-600">Select a course to stream production logs. (Test pipeline logs are written to backend console).</div>
            ) : logs.length === 0 ? (
              <div className="text-zinc-600">Waiting for logs...</div>
            ) : (
              logs.map((log, i) => <div key={i}>{log}</div>)
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
