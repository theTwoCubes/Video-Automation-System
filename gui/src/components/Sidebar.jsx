import { NavLink } from 'react-router-dom';
import { LayoutDashboard, FlaskConical, Video, Settings, HelpCircle, Box } from 'lucide-react';

export function Sidebar() {
  return (
    <nav className="w-64 bg-zinc-950 border-r border-zinc-900 flex flex-col h-full">
      <div className="p-6 border-b border-zinc-900">
        <div className="flex items-center gap-3 text-zinc-100 font-semibold tracking-tight text-lg">
          <img
            src="/TabIcon.png"
            alt="Logo"
            className="w-6 h-6 object-contain"
          />
          theTwoCubes
        </div>
        <div className="text-xs text-zinc-500 mt-1">Video Automation System</div>
      </div>

      <div className="flex-1 p-4 flex flex-col gap-1 overflow-y-auto">
        <NavLink to="/" className={({ isActive }) => `flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors ${isActive ? 'bg-zinc-900 text-white' : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/50'}`}>
          <LayoutDashboard className="w-4 h-4" /> Dashboard
        </NavLink>
        <NavLink to="/curricula" className={({ isActive }) => `flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors ${isActive ? 'bg-zinc-900 text-white' : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/50'}`}>
          <FlaskConical className="w-4 h-4" /> Curricula
        </NavLink>
        <NavLink to="/pipeline" className={({ isActive }) => `flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors ${isActive ? 'bg-zinc-900 text-white' : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/50'}`}>
          <Video className="w-4 h-4" /> Pipeline Monitor
        </NavLink>
      </div>

      <div className="p-4 border-t border-zinc-900 flex flex-col gap-1">
        <NavLink to="/settings" className={({ isActive }) => `flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors ${isActive ? 'bg-zinc-900 text-white' : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/50'}`}>
          <Settings className="w-4 h-4" /> Settings
        </NavLink>
        <NavLink to="/help" className={({ isActive }) => `flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors ${isActive ? 'bg-zinc-900 text-white' : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/50'}`}>
          <HelpCircle className="w-4 h-4" /> Documentation
        </NavLink>
      </div>
    </nav>
  );
}
