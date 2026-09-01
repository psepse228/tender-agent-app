// Thin fetch wrapper around the FastAPI backend. Auth is entirely the
// `tender_agent_session` HttpOnly cookie (see backend/app/auth/dependencies.py)
// -- same-origin `fetch` sends it automatically, so no Authorization header
// is ever needed here. A 401 anywhere means the cookie is missing/expired;
// the only correct move is a full navigation to the server-rendered /login
// page (not a React route -- login itself, incl. the Google OAuth bounce,
// lives entirely on the backend).
import type { ChatMessage, Source, Tender } from './types';
import { normalizeFavorite, normalizeTender } from './types';

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  });

  if (res.status === 401) {
    window.location.href = '/login';
    // Never resolves -- the navigation above is about to tear this page down.
    return new Promise<T>(() => {});
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}) as Record<string, unknown>);
    throw new ApiError(res.status, typeof body.detail === 'string' ? body.detail : `Request failed (${res.status})`);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export { ApiError };

// ── auth ──
export interface Me {
  email: string | null;
  picture: string | null;
}
export const getMe = () => request<Me>('/api/auth/me');
export const logout = () => request<{ ok: true }>('/api/auth/logout', { method: 'POST' });
export const exchangeToken = (token: string) =>
  fetch('/api/auth/exchange-token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
  }).then((res) => res.ok);

// ── tenders ──
interface TendersResponse {
  tenders?: unknown[];
}
function normalizeTendersResponse(data: TendersResponse | unknown[]): Tender[] {
  const raw = Array.isArray(data) ? data : data.tenders || [];
  return raw
    .map((t) => normalizeTender(t as Record<string, unknown>))
    .filter((t) => t.title && t.title !== 'Без названия' && t.matchPercent > 0);
}
export const getTenders = () => request<TendersResponse | unknown[]>('/api/tenders').then(normalizeTendersResponse);

export interface RefreshSourceStatus {
  name: string;
  status: 'ok' | 'failed' | string;
}
export interface RefreshResult {
  tenders: Tender[];
  sourcesStatus: RefreshSourceStatus[];
}
export async function refreshTenders(signal?: AbortSignal): Promise<RefreshResult> {
  const res = await fetch('/api/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: '{}',
    signal,
  });
  if (res.status === 401) {
    window.location.href = '/login';
    return new Promise(() => {});
  }
  if (res.status === 429) throw new ApiError(429, 'rate limited');
  if (!res.ok) throw new ApiError(res.status, `Request failed (${res.status})`);
  const data = (await res.json()) as TendersResponse & { sources_status?: RefreshSourceStatus[] };
  return { tenders: normalizeTendersResponse(data), sourcesStatus: data.sources_status || [] };
}

export interface RefreshProgress {
  total: number;
  done: number;
  sources: RefreshSourceStatus[];
}
export const getRefreshStatus = () => request<RefreshProgress>('/api/refresh/status');

// ── profile ──
export const getProfile = () => request<{ profile_text: string | null }>('/api/profile');

// ── profile chat (Скаут AI) ──
export const getProfileChat = () => request<{ messages: ChatMessage[] }>('/api/profile-chat');
export const postProfileChat = (message: string) =>
  request<{ reply: string }>('/api/profile-chat', { method: 'POST', body: JSON.stringify({ message }) });

// ── favorites (Ваш пакет) ──
export const getFavorites = () =>
  request<{ favorites?: unknown[] }>('/api/favorites').then((d) => (d.favorites || []).map((f) => normalizeFavorite(f as Record<string, unknown>)));
export const addFavorite = (tenderId: string) =>
  request<{ favorite_id: string; already_existed?: boolean }>('/api/favorites', {
    method: 'POST',
    body: JSON.stringify({ tender_id: tenderId }),
  });
export const removeFavorite = (favoriteId: string) => request<void>(`/api/favorites/${favoriteId}`, { method: 'DELETE' });
export const getFavoriteChat = (favoriteId: string) => request<{ messages: ChatMessage[] }>(`/api/favorites/${favoriteId}/chat`);
export const postFavoriteChat = (favoriteId: string, message: string) =>
  request<{ reply: string }>(`/api/favorites/${favoriteId}/chat`, { method: 'POST', body: JSON.stringify({ message }) });

// ── sources ──
export const getSources = () => request<{ sources?: Source[] }>('/api/sources').then((d) => d.sources || []);
export const addSource = (name: string, url: string) =>
  request<Source>('/api/sources', { method: 'POST', body: JSON.stringify({ name, url }) });
export const removeSource = (id: string) => request<void>(`/api/sources/${id}`, { method: 'DELETE' });

// ── stats / billing ──
export const getStats = () => request<{ subscriptionStatus?: string }>('/api/stats');

// ── telegram link (notifications only, never a login path) ──
export const getTelegramLinkStatus = () => request<{ linked: boolean }>('/api/link-telegram');
export const linkTelegram = (initData: string) =>
  request<{ ok: true }>('/api/link-telegram', { method: 'POST', body: JSON.stringify({ init_data: initData }) });
