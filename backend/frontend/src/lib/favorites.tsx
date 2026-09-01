import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import * as api from './api';
import { favoriteKey, type Favorite, type Tender } from './types';

interface FavoritesState {
  favorites: Favorite[];
  loading: boolean;
  loaded: boolean;
  refresh: () => Promise<void>;
  /** The favorite row matching a Tenders-list card, if it's already in Ваш пакет. */
  findFor: (t: Tender) => Favorite | undefined;
  add: (tenderId: string) => Promise<{ favoriteId: string; alreadyExisted: boolean }>;
  remove: (favoriteId: string) => Promise<void>;
}

const FavoritesContext = createContext<FavoritesState | null>(null);

export function FavoritesProvider({ children }: { children: ReactNode }) {
  const [favorites, setFavorites] = useState<Favorite[]>([]);
  const [loading, setLoading] = useState(true);
  const [loaded, setLoaded] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setFavorites(await api.getFavorites());
    } finally {
      setLoading(false);
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const findFor = useCallback((t: Tender) => favorites.find((f) => favoriteKey(f) === favoriteKey(t)), [favorites]);

  const add = useCallback(async (tenderId: string) => {
    const res = await api.addFavorite(tenderId);
    await refresh();
    return { favoriteId: res.favorite_id, alreadyExisted: !!res.already_existed };
  }, [refresh]);

  const remove = useCallback(async (favoriteId: string) => {
    await api.removeFavorite(favoriteId);
    setFavorites((prev) => prev.filter((f) => f.id !== favoriteId));
  }, []);

  return (
    <FavoritesContext.Provider value={{ favorites, loading, loaded, refresh, findFor, add, remove }}>
      {children}
    </FavoritesContext.Provider>
  );
}

export function useFavorites() {
  const ctx = useContext(FavoritesContext);
  if (!ctx) throw new Error('useFavorites must be used within FavoritesProvider');
  return ctx;
}
