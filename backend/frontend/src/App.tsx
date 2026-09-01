import { useEffect, useState } from 'react';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { SessionProvider, useSession } from './lib/session';
import { FavoritesProvider } from './lib/favorites';
import { TendersProvider } from './lib/tenders';
import { ToastProvider } from './lib/toast';
import { RefreshControlProvider } from './lib/refreshControl';
import { BootSplash } from './components/BootSplash';
import Layout from './components/Layout';
import Tenders from './pages/Tenders';
import Favorites from './pages/Favorites';
import TenderDetail from './pages/TenderDetail';
import Profile from './pages/Profile';
import Methodology from './pages/Methodology';
import { useTelegramInit } from './lib/useTelegramInit';

// A branded splash for at least this long, even once the session resolves
// instantly (e.g. an already-cached session) -- the previous vanilla
// frontend's own loader had the same deliberate floor (see its 700ms
// setTimeout before removing #loader): flashing the mark for a single
// frame reads as broken, not fast.
const MIN_SPLASH_MS = 550;

export default function App() {
  useTelegramInit();

  return (
    <ToastProvider>
      <SessionProvider>
        <FavoritesProvider>
          <TendersProvider>
            <RefreshControlProvider>
              <BrowserRouter>
                <Gate />
              </BrowserRouter>
            </RefreshControlProvider>
          </TendersProvider>
        </FavoritesProvider>
      </SessionProvider>
    </ToastProvider>
  );
}

function Gate() {
  const { loading } = useSession();
  const [minTimeElapsed, setMinTimeElapsed] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setMinTimeElapsed(true), MIN_SPLASH_MS);
    return () => clearTimeout(t);
  }, []);

  return (
    <>
      <BootSplash show={loading || !minTimeElapsed} />
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Tenders />} />
          <Route path="/favorites" element={<Favorites />} />
          <Route path="/tenders/:id" element={<TenderDetail />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="/methodology" element={<Methodology />} />
        </Route>
      </Routes>
    </>
  );
}
