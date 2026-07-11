import { useFetch } from '../hooks/useFetch';
import { S, cx } from '../lib/ui';

const API = 'http://localhost:8000/api';

// Settings - render profiles, voices, and live LLM usage. Gives the sidebar's
// "Settings" link a real destination (it previously dead-ended, redirecting
// home) without inventing write operations that need their own QA.
export function Settings() {
  const { data: profiles } = useFetch(`${API}/profiles`);
  const { data: voices }   = useFetch(`${API}/voices`);
  const { data: usage }    = useFetch(`${API}/usage`);

  return (
    <div className="min-h-screen bg-black text-zinc-200 p-8" style={{ fontFamily: "'Inter', sans-serif" }}>
      <div className="max-w-4xl mx-auto space-y-8">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <div className="w-1.5 h-5 bg-teal-400 rounded-full" />
            <h1 className="text-xl font-bold text-white tracking-tight">Settings</h1>
          </div>
          <p className="text-zinc-600 text-[13px] ml-4">Render profiles, voices, and LLM usage.</p>
        </div>

        <div>
          <span className={S.label}>Render Profiles</span>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-2">
            {(profiles || []).map(p => (
              <div key={p.name} className={cx(S.card, 'px-4 py-3')}>
                <div className="text-[13px] font-semibold text-white">{p.name}</div>
                <div className="text-[11px] text-zinc-600 mt-0.5">{p.description || '—'}</div>
              </div>
            ))}
            {!profiles?.length && <div className="text-zinc-700 text-[13px]">No profiles found.</div>}
          </div>
        </div>

        <div>
          <span className={S.label}>Voices</span>
          <div className="flex flex-wrap gap-2 mt-2">
            {(voices || []).map(v => (
              <span key={v.id} className={cx(S.card, 'px-3 py-1.5 text-[12px] text-zinc-300')}>{v.name}</span>
            ))}
            {!voices?.length && <div className="text-zinc-700 text-[13px]">No voices found.</div>}
          </div>
        </div>

        {usage && (
          <div>
            <span className={S.label}>LLM Usage</span>
            <div className={cx(S.card, 'px-5 py-4 flex items-center gap-8 flex-wrap mt-2')}>
              {Object.entries(usage).map(([k, val]) => (
                <div key={k} className="text-[12px]">
                  <span className="text-zinc-500">{k}: </span>
                  <span className="text-zinc-200 font-medium tabular-nums">
                    {typeof val === 'number' ? val.toLocaleString() : String(val)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
