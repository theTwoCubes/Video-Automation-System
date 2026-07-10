import { useState, useEffect, useCallback } from 'react';

export function useFetch(url, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    if (!url) return;
    setLoading(true);
    fetch(url)
      .then(r => { if (!r.ok) throw new Error(`${r.status}`); return r.json(); })
      .then(d => { setData(d); setLoading(false); setError(null); })
      .catch(e => { setError(e.message); setLoading(false); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, ...deps]);

  useEffect(() => { load(); }, [load]);
  return { data, loading, error, refresh: load };
}

export function usePolling(url, intervalMs = 2000, enabled = true) {
  const [data, setData] = useState(null);
  useEffect(() => {
    if (!enabled || !url) return;
    let id;
    const tick = () => {
      fetch(url)
        .then(r => r.json())
        .then(d => {
          setData(d);
          if (d?.status === 'done' || d?.status === 'failed') {
            if (id) clearInterval(id);
          }
        })
        .catch(() => {});
    };
    tick();
    id = setInterval(tick, intervalMs);
    return () => clearInterval(id);
  }, [url, intervalMs, enabled]);
  return data;
}
