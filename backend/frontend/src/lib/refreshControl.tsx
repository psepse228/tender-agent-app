import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';

// The ↻ refresh button lives in the header (shared across every route) but
// only ever does something on the Тендеры screen -- this lets that screen
// hand its refresh handler up to the header while it's mounted, instead of
// the header needing route-specific knowledge of what "refresh" means.
interface RefreshControl {
  onRefresh: (() => void) | null;
  spinning: boolean;
}

interface RefreshControlContextValue extends RefreshControl {
  setControl: (control: RefreshControl | null) => void;
}

const RefreshControlContext = createContext<RefreshControlContextValue | null>(null);

export function RefreshControlProvider({ children }: { children: ReactNode }) {
  const [control, setControl] = useState<RefreshControl | null>(null);
  return (
    <RefreshControlContext.Provider value={{ onRefresh: control?.onRefresh ?? null, spinning: control?.spinning ?? false, setControl }}>
      {children}
    </RefreshControlContext.Provider>
  );
}

export function useRefreshControl() {
  const ctx = useContext(RefreshControlContext);
  if (!ctx) throw new Error('useRefreshControl must be used within RefreshControlProvider');
  return ctx;
}

/** Call from the screen that owns refresh (Tenders) -- registers while
 * mounted, clears on unmount so other screens correctly hide the button. */
export function useRegisterRefreshControl(onRefresh: (() => void) | null, spinning: boolean) {
  const { setControl } = useRefreshControl();
  useEffect(() => {
    setControl({ onRefresh, spinning });
    return () => setControl(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onRefresh, spinning]);
}
