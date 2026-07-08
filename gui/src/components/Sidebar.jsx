import { NavLink } from 'react-router-dom';
import { LayoutDashboard, BookOpen, FlaskConical, Video, Settings, HelpCircle } from 'lucide-react';

export function Sidebar() {
  return (
    <nav className="sidebar">
      <div className="sidebar-logo">
        <div className="brand">
          <div className="cube-icon" />
          theTwoCubes
        </div>
        <div className="sub">Video Automation System</div>
      </div>
      
      <div className="sidebar-nav">
        <NavLink to="/" className={({isActive}) => isActive ? "nav-item active" : "nav-item"}>
          <LayoutDashboard /> Dashboard
        </NavLink>
        <NavLink to="/knowledge" className={({isActive}) => isActive ? "nav-item active" : "nav-item"}>
          <BookOpen /> Knowledge Base
        </NavLink>
        <NavLink to="/curricula" className={({isActive}) => isActive ? "nav-item active" : "nav-item"}>
          <FlaskConical /> Curricula
        </NavLink>
        <NavLink to="/pipeline" className={({isActive}) => isActive ? "nav-item active" : "nav-item"}>
          <Video /> Pipeline Monitor
        </NavLink>
      </div>

      <div className="sidebar-footer">
        <NavLink to="/settings" className={({isActive}) => isActive ? "nav-item active" : "nav-item"}>
          <Settings /> Settings
        </NavLink>
        <NavLink to="/help" className={({isActive}) => isActive ? "nav-item active" : "nav-item"}>
          <HelpCircle /> Documentation
        </NavLink>
      </div>
    </nav>
  );
}
