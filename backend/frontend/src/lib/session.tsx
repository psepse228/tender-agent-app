import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import * as api from './api';
import { getStartParam } from './telegram';

interface SessionState {
  loading: boolean;
  email: string | null;
  picture: string | null;
  logout: () => Promise<void>;
}

const SessionContext = createContext<SessionState | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState<string | null>(null);
  const [picture, setPicture] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function boot() {
      // After escaping to the real browser for Google login on mobile (see
      // /login), Telegram reopens the Mini App via a `startapp` deep link
      // carrying a one-time exchange token -- this is the one request that
      // runs *inside* the Mini App's own webview and can actually set the
      // session cookie there. Must happen before reading /api/auth/me.
      const token = getStartParam();
      if (token) await api.exchangeToken(token).catch(() => false);

      // /api/auth/me never 401s (it reports {email: null} instead) -- actual
      // route protection happens per-request in lib/api.ts's 401 handler.
      // This call is only for the account menu / logout UI.
      const me = await api.getMe().catch(() => ({ email: null, picture: null }));
      if (cancelled) return;
      setEmail(me.email);
      setPicture(me.picture);
      setLoading(false);
    }

    boot();
    return () => {
      cancelled = true;
    };
  }, []);

  async function logout() {
    await api.logout();
    window.location.href = '/login';
  }

  return <SessionContext.Provider value={{ loading, email, picture, logout }}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error('useSession must be used within SessionProvider');
  return ctx;
}
