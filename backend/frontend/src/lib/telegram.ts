// Thin wrapper around window.Telegram.WebApp.
//
// Unlike TD Webster, Telegram here is NOT a login mechanism -- the backend
// is cookie-only auth (Google OAuth session, see
// backend/app/auth/dependencies.py). Telegram's WebApp SDK is only used for:
//   - matching Telegram's own chrome (safe-area insets, vertical-swipe lock)
//   - the "connect Telegram for notifications" banner (a secondary link,
//     not a sign-in path -- see /api/link-telegram)
//   - completing the one-time deep-link handback after escaping to the
//     real browser for Google login on mobile (see session.tsx)
export interface TelegramWebApp {
  initData: string;
  initDataUnsafe: { start_param?: string };
  platform: string;
  ready: () => void;
  expand: () => void;
  onEvent: (event: string, cb: () => void) => void;
  openLink: (url: string) => void;
  disableVerticalSwipes?: () => void;
  safeAreaInset?: { top: number; bottom: number; left: number; right: number };
  contentSafeAreaInset?: { top: number; bottom: number; left: number; right: number };
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebApp };
  }
}

export function getWebApp(): TelegramWebApp | undefined {
  return window.Telegram?.WebApp;
}

export function getInitData(): string | undefined {
  return getWebApp()?.initData || undefined;
}

export function getStartParam(): string | undefined {
  return getWebApp()?.initDataUnsafe?.start_param || undefined;
}

export function openLink(url: string | undefined | null) {
  if (!url) return;
  const full = url.startsWith('http') ? url : `https://${url}`;
  const tg = getWebApp();
  if (tg) tg.openLink(full);
  else window.open(full, '_blank', 'noopener');
}

/** Call once at app startup, no-ops outside Telegram. */
export function initTelegram() {
  const tg = getWebApp();
  if (!tg) return;
  tg.ready();
  tg.expand();

  // Main App mode renders fullscreen -- Telegram floats its own close/menu
  // chrome and the OS status bar on top of our content instead of pushing
  // it down, so without this our header sits right under (or behind) them.
  // safeAreaInset covers the device notch/status bar, contentSafeAreaInset
  // covers Telegram's own floating controls on top of that -- both are
  // summed into one CSS var so the header can just pad around them.
  const applySafeArea = () => {
    const top = (tg.safeAreaInset?.top || 0) + (tg.contentSafeAreaInset?.top || 0);
    document.documentElement.style.setProperty('--tg-safe-top', `${top}px`);
  };
  applySafeArea();
  tg.onEvent('safeAreaChanged', applySafeArea);
  tg.onEvent('contentSafeAreaChanged', applySafeArea);

  // Fullscreen Main App mode otherwise treats a downward swipe anywhere as
  // "minimize/close the Mini App", which eats the bottom sheet's own
  // swipe-to-dismiss gesture and closes the whole app instead of the sheet.
  tg.disableVerticalSwipes?.();
}
