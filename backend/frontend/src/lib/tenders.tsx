import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import * as api from './api';
import { favoriteKey, type Tender } from './types';

interface TendersState {
  tenders: Tender[];
  loading: boolean;
  loaded: boolean;
  needsProfile: boolean;
  refresh: () => Promise<{ found: number; failed: string[] } | null>;
  /** Other tenders from the same organization, currently loaded -- powers
   * "Похожие тендеры этого заказчика" on the tender detail page. Purely
   * client-side (cross-referencing tenders already fetched), not a new
   * backend capability. */
  fromSameOrg: (t: Tender) => Tender[];
}

const TendersContext = createContext<TendersState | null>(null);

// Lifted out of the Тендеры page into a shared context so the tender
// detail page (reached from either Тендеры or Пакет) can look up "other
// tenders from this organization" without re-fetching -- the whole app
// shares one already-loaded list instead of each screen keeping its own.
export function TendersProvider({ children }: { children: ReactNode }) {
  const [tenders, setTenders] = useState<Tender[]>([]);
  const [loading, setLoading] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [needsProfile, setNeedsProfile] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getTenders();
      setTenders(data);
      if (data.length === 0) {
        const profile = await api.getProfile().catch(() => ({ profile_text: '' }));
        setNeedsProfile(!profile.profile_text);
      } else {
        setNeedsProfile(false);
      }
    } finally {
      setLoading(false);
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const refresh = useCallback(async () => {
    const { tenders: fresh, sourcesStatus } = await api.refreshTenders();
    const failed = sourcesStatus.filter((s) => s.status === 'failed').map((s) => s.name);
    if (fresh.length > 0) setTenders(fresh);
    return { found: fresh.length, failed };
  }, []);

  const fromSameOrg = useCallback(
    (t: Tender) => {
      // Excludes by title+organization, not raw id: `t` here can be a
      // favorite row (whose id is the favorite's own, not the originating
      // tender's -- see favoriteKey) viewed via the same detail page --
      // comparing ids would let the tender show up in its own "similar"
      // list under its other id.
      const key = favoriteKey(t);
      return tenders.filter((x) => favoriteKey(x) !== key && x.organization && x.organization === t.organization);
    },
    [tenders]
  );

  return (
    <TendersContext.Provider value={{ tenders, loading, loaded, needsProfile, refresh, fromSameOrg }}>
      {children}
    </TendersContext.Provider>
  );
}

export function useTenders() {
  const ctx = useContext(TendersContext);
  if (!ctx) throw new Error('useTenders must be used within TendersProvider');
  return ctx;
}
