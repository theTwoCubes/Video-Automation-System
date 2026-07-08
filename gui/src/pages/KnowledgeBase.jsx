import { useState } from 'react';
import { BookOpen, Upload, FileText, Globe, Loader2 } from 'lucide-react';
import { useFetch } from '../hooks/useFetch';

const API = 'http://localhost:8000/api';

export function KnowledgeBase() {
  const [source, setSource] = useState('');
  const [name, setName] = useState('');
  const [topic, setTopic] = useState('');
  const [tags, setTags] = useState('');
  const [type, setType] = useState('pdf');
  const [taskId, setTaskId] = useState(null);
  
  const { data: statusData, refresh } = useFetch(taskId ? `${API}/ingest/${taskId}` : null, [taskId]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API}/ingest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source, name, topic, source_type: type, tags }),
      });
      const data = await res.json();
      if (data.task_id) {
        setTaskId(data.task_id);
        const iv = setInterval(() => {
          refresh();
        }, 2000);
      }
    } catch (e) {
      alert("Failed to start ingestion");
    }
  };

  const isDone = statusData?.status === 'done' || statusData?.status === 'failed';

  return (
    <div className="main">
      <header className="topbar">
        <BookOpen size={18} />
        <h1 className="topbar-title">Knowledge Base Ingestion</h1>
      </header>

      <main className="content">
        <div className="card max-w-2xl">
          <h2 className="card-title">Add Knowledge Source</h2>
          <p className="text-dim mb-4">Ingest a PDF book, URL, or markdown directory into the vector store.</p>
          
          <form onSubmit={handleSubmit} className="form-grid">
            <div className="form-group">
              <label>Source Type</label>
              <select value={type} onChange={e => setType(e.target.value)} className="input" disabled={taskId && !isDone}>
                <option value="pdf">PDF File (Path)</option>
                <option value="url">Website URL</option>
                <option value="markdown_dir">Markdown Directory</option>
              </select>
            </div>
            
            <div className="form-group">
              <label>Source Path or URL</label>
              <input required value={source} onChange={e => setSource(e.target.value)} className="input" placeholder="/path/to/book.pdf" disabled={taskId && !isDone} />
            </div>

            <div className="form-group">
              <label>Source Name</label>
              <input required value={name} onChange={e => setName(e.target.value)} className="input" placeholder="e.g., C++ Primer" disabled={taskId && !isDone} />
            </div>

            <div className="form-group">
              <label>Primary Topic</label>
              <input required value={topic} onChange={e => setTopic(e.target.value)} className="input" placeholder="e.g., C++" disabled={taskId && !isDone} />
            </div>

            <div className="form-group">
              <label>Tags (Comma separated)</label>
              <input value={tags} onChange={e => setTags(e.target.value)} className="input" placeholder="programming, backend" disabled={taskId && !isDone} />
            </div>

            <button type="submit" className="btn btn-primary mt-2" disabled={taskId && !isDone}>
              <Upload size={16} /> Start Ingestion
            </button>
          </form>

          {taskId && (
            <div className="mt-6 p-4 rounded bg-surface border">
              <h3 className="font-semibold mb-2">Ingestion Status</h3>
              {statusData?.status === 'running' && (
                <div className="flex items-center gap-2 text-warning">
                  <Loader2 size={16} className="spin" /> Parsing and embedding into ChromaDB...
                </div>
              )}
              {statusData?.status === 'done' && (
                <div className="text-success">
                  ✓ Successfully ingested! Source ID: <code>{statusData.source_id}</code>
                  <br/><br/>
                  You can now head to the Curricula tab to generate a course using this source.
                </div>
              )}
              {statusData?.status === 'failed' && (
                <div className="text-error">
                  ✗ Ingestion failed: {statusData.error}
                </div>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
