import { NavLink } from 'react-router-dom';

const links = [
  { to: '/',        icon: '⊞', label: 'Dashboard'       },
  { to: '/pipeline', icon: '◉', label: 'Pipeline'        },
  { to: '/testing',  icon: '⬡', label: 'Testing Studio', accent: true },
];

// Settings routes to a real page; Docs opens the live FastAPI reference. Both
// previously pointed at nonexistent routes that silently redirected home.
const bottom = [
  { to: '/settings', icon: '⊙', label: 'Settings' },
  { href: 'http://localhost:8000/docs', icon: '◎', label: 'API Docs', external: true },
];

export function Sidebar() {
  return (
    <nav
      className="w-56 flex-shrink-0 border-r border-[#111] flex flex-col h-full bg-black"
      style={{ fontFamily: "'Inter', sans-serif" }}
    >
      {/* Logo */}
      <div className="px-5 py-5 border-b border-[#111]">
        <div className="flex items-center gap-2.5">
          <img src="/TabIcon.png" alt="Logo" className="w-6 h-6 object-contain flex-shrink-0" />
          <span className="text-[13px] font-bold text-white tracking-tight">theTwoCubes</span>
        </div>
        <div className="text-[10px] text-zinc-700 mt-0.5 ml-8 tracking-wide">Video Automation</div>
      </div>

      {/* Primary nav */}
      <div className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {links.map(({ to, icon, label, accent }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              [
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-[13px] font-medium transition-all duration-150',
                isActive
                  ? accent
                    ? 'bg-teal-500/10 text-teal-400 border border-teal-500/20'
                    : 'bg-[#111] text-white border border-[#1e1e1e]'
                  : 'text-zinc-500 hover:text-zinc-200 hover:bg-[#0d0d0d]',
              ].join(' ')
            }
          >
            <span className="text-base leading-none w-4 text-center flex-shrink-0">{icon}</span>
            {label}
          </NavLink>
        ))}
      </div>

      {/* Bottom links */}
      <div className="px-3 py-4 border-t border-[#111] space-y-0.5">
        {bottom.map((item) => item.external ? (
          <a
            key={item.href}
            href={item.href}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-3 px-3 py-2 rounded-lg text-[12px] text-zinc-600 hover:text-zinc-400 transition-all duration-150"
          >
            <span className="text-sm leading-none w-4 text-center flex-shrink-0">{item.icon}</span>
            {item.label}
          </a>
        ) : (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              [
                'flex items-center gap-3 px-3 py-2 rounded-lg text-[12px] transition-all duration-150',
                isActive ? 'text-zinc-300' : 'text-zinc-600 hover:text-zinc-400',
              ].join(' ')
            }
          >
            <span className="text-sm leading-none w-4 text-center flex-shrink-0">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
