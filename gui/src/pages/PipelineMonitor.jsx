import { useState, useEffect } from 'react';
import { Video, Terminal, Play, Loader2, RefreshCw } from 'lucide-react';
import { useFetch, usePolling } from '../hooks/useFetch';

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
    <div className="main">
      <header className="topbar">
        <Video size={18} />
        <h1 className="topbar-title">Pipeline Monitor</h1>
      </header>

      <main className="content flex gap-6">
        <div className="flex-1" style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="card mb-6">
            <h2 className="card-title">Run Production Generation</h2>
            <div className="flex gap-4 items-end">
              <div className="form-group flex-1" style={{ marginBottom: 0 }}>
                <label>Select Course</label>
                <select value={selectedCourse} onChange={e => setSelectedCourse(e.target.value)} className="input">
                  <option value="">-- Select a course --</option>
                  {courses?.map(c => (
                    <option key={c.id} value={c.id}>{c.title}</option>
                  ))}
                </select>
              </div>
              <button className="btn btn-primary" disabled={!selectedCourse} onClick={handleStartGeneration}>
                <Play size={16} /> Run Next Lesson
              </button>
            </div>
          </div>

          <div className="card mb-6">
            <h2 className="card-title">Run Automated Test (Offline Data)</h2>
            <p className="text-dim mb-4">Run the pipeline using cached LLM outputs from tests/fixtures to test rendering without spending API credits.</p>
            <div className="flex gap-4 items-end">
              <button className="btn btn-outline" onClick={async () => {
                try {
                  const res = await fetch(`${API}/test/run`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ fixture_path: 'tests/fixtures/cpp_variables_lesson.json', force_restart: true, from_step: 'slides' })
                  });
                  const d = await res.json();
                  if(d.run_id) alert('Test pipeline started! Check backend console for logs.');
                } catch(e) { alert('Failed to start test'); }
              }}>
                <Play size={16} /> Run Test (C++ Variables)
              </button>
            </div>
          </div>
        </div>

        <div className="card flex-1" style={{ height: 'calc(100vh - 120px)', display: 'flex', flexDirection: 'column', padding: 0 }}>
          <div className="topbar" style={{ borderTop: 'none', borderLeft: 'none', borderRight: 'none', background: 'var(--surface2)' }}>
            <div className="topbar-title text-sm font-mono flex items-center gap-2">
              <Terminal size={14} /> Live Logs {selectedCourse ? `(${selectedCourse})` : ''}
            </div>
          </div>
          <div className="terminal-logs" style={{ flex: 1, overflowY: 'auto', padding: '20px', background: '#000', color: '#0f0', fontFamily: 'monospace', fontSize: '13px', lineHeight: '1.6' }}>
            {!selectedCourse ? (
              <div style={{ color: '#555' }}>Select a course to stream production logs. (Test pipeline logs are written to backend console).</div>
            ) : logs.length === 0 ? (
              <div style={{ color: '#555' }}>Waiting for logs...</div>
            ) : (
              logs.map((log, i) => <div key={i}>{log}</div>)
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
