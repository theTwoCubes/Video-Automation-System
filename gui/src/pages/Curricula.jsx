import { useState } from 'react';
import { FlaskConical, Play, Save } from 'lucide-react';
import { useFetch } from '../hooks/useFetch';

const API = 'http://localhost:8000/api';

export function Curricula() {
  const [sourceId, setSourceId] = useState('');
  const [topic, setTopic] = useState('');
  const [audience, setAudience] = useState('beginners');
  const [minLessons, setMinLessons] = useState(30);
  const [taskId, setTaskId] = useState(null);
  const [editingCourse, setEditingCourse] = useState(null);
  const [editedJson, setEditedJson] = useState('');

  const { data: statusData, refresh } = useFetch(taskId ? `${API}/curricula/tasks/${taskId}` : null, [taskId]);
  const { data: courses, refresh: refreshCourses } = useFetch(`${API}/courses`);

  const handleGenerate = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API}/curricula/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_id: sourceId, topic, target_audience: audience, min_lessons: minLessons }),
      });
      const data = await res.json();
      if (data.task_id) {
        setTaskId(data.task_id);
        const iv = setInterval(() => {
          refresh();
        }, 3000);
      }
    } catch (e) {
      alert("Failed to start curriculum generation");
    }
  };

  const loadEditor = async (courseId) => {
    // In a real app we'd fetch the raw curriculum JSON. 
    // Here we'll just mock it or if we added an endpoint for GET curriculum we'd hit it.
    // Since we don't have a GET raw curriculum endpoint yet, we'll just show the UI structure.
    setEditingCourse(courseId);
    setEditedJson('{\n  "module": "Example",\n  "lessons": []\n}'); 
  };

  const handleSave = async () => {
    try {
      await fetch(`${API}/courses/${editingCourse}/curriculum`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ curriculum: editedJson })
      });
      alert('Saved!');
      setEditingCourse(null);
      refreshCourses();
    } catch(e) {
      alert('Failed to save');
    }
  }

  const isDone = statusData?.status === 'done' || statusData?.status === 'failed';

  return (
    <div className="main">
      <header className="topbar">
        <FlaskConical size={18} />
        <h1 className="topbar-title">Curriculum Generation</h1>
      </header>

      <main className="content flex gap-6">
        <div className="card flex-1">
          <h2 className="card-title">Generate New Course</h2>
          <form onSubmit={handleGenerate} className="form-grid">
            <div className="form-group">
              <label>Source ID (from Knowledge Base)</label>
              <input required value={sourceId} onChange={e => setSourceId(e.target.value)} className="input" placeholder="uuid..." disabled={taskId && !isDone} />
            </div>
            
            <div className="form-group">
              <label>Course Topic</label>
              <input required value={topic} onChange={e => setTopic(e.target.value)} className="input" placeholder="e.g., C++" disabled={taskId && !isDone} />
            </div>

            <div className="form-group">
              <label>Target Audience</label>
              <input required value={audience} onChange={e => setAudience(e.target.value)} className="input" placeholder="beginners" disabled={taskId && !isDone} />
            </div>

            <div className="form-group">
              <label>Target Min Lessons</label>
              <input type="number" required value={minLessons} onChange={e => setMinLessons(Number(e.target.value))} className="input" disabled={taskId && !isDone} />
            </div>

            <button type="submit" className="btn btn-primary mt-2" disabled={taskId && !isDone}>
              <Play size={16} /> Generate Curriculum
            </button>
          </form>

          {taskId && (
            <div className="mt-6 p-4 rounded bg-surface border">
              <h3 className="font-semibold mb-2">Generation Status</h3>
              {statusData?.status === 'running' && (
                <div className="text-warning">Running multi-pass generation... This may take a few minutes.</div>
              )}
              {statusData?.status === 'done' && (
                <div className="text-success">
                  ✓ Successfully generated {statusData.curriculum?.total_lessons} lessons!
                </div>
              )}
              {statusData?.status === 'failed' && (
                <div className="text-error">✗ Failed: {statusData.error}</div>
              )}
            </div>
          )}
        </div>

        <div className="card flex-1" style={{ display: 'flex', flexDirection: 'column' }}>
          <h2 className="card-title">Curriculum Editor</h2>
          {!editingCourse ? (
            <div className="empty-state" style={{ flex: 1, justifyContent: 'center' }}>
              <p className="text-dim">Select a generated course from the Dashboard to edit its curriculum.</p>
              <div className="mt-4 flex flex-col gap-2">
                {courses?.map(c => (
                  <button key={c.id} className="btn btn-outline w-full justify-start" onClick={() => loadEditor(c.id)}>
                    Edit: {c.title}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
              <div className="flex justify-between items-center mb-2">
                <span className="font-semibold">Editing: {editingCourse}</span>
                <button className="btn btn-primary btn-sm" onClick={handleSave}><Save size={14}/> Save</button>
              </div>
              <textarea 
                className="input" 
                style={{ flex: 1, fontFamily: 'monospace', minHeight: '300px', resize: 'none' }}
                value={editedJson}
                onChange={(e) => setEditedJson(e.target.value)}
              />
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
