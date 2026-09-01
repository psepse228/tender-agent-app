import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { SessionProvider } from './lib/session';
import { FavoritesProvider } from './lib/favorites';
import { ToastProvider } from './lib/toast';
import { RefreshControlProvider } from './lib/refreshControl';
import Layout from './components/Layout';
import Tenders from './pages/Tenders';
import Favorites from './pages/Favorites';
import FavoriteDetail from './pages/FavoriteDetail';
import Scout from './pages/Scout';
import Sources from './pages/Sources';
import Methodology from './pages/Methodology';
import { useTelegramInit } from './lib/useTelegramInit';

export default function App() {
  useTelegramInit();

  return (
    <ToastProvider>
      <SessionProvider>
        <FavoritesProvider>
          <RefreshControlProvider>
            <BrowserRouter>
              <Routes>
                <Route element={<Layout />}>
                  <Route path="/" element={<Tenders />} />
                  <Route path="/favorites" element={<Favorites />} />
                  <Route path="/favorites/:id" element={<FavoriteDetail />} />
                  <Route path="/scout" element={<Scout />} />
                  <Route path="/sources" element={<Sources />} />
                  <Route path="/methodology" element={<Methodology />} />
                </Route>
              </Routes>
            </BrowserRouter>
          </RefreshControlProvider>
        </FavoritesProvider>
      </SessionProvider>
    </ToastProvider>
  );
}
