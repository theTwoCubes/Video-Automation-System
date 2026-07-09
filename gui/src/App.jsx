import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { Dashboard } from './pages/Dashboard';
import { Curricula } from './pages/Curricula';
import { PipelineMonitor } from './pages/PipelineMonitor';
import { TestingStudio } from './pages/TestingStudio';
import './index.css';

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen overflow-hidden bg-black text-zinc-200">
        <Sidebar />
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/curricula/:courseId" element={<Curricula />} />
            <Route path="/pipeline" element={<PipelineMonitor />} />
            <Route path="/testing" element={<TestingStudio />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
