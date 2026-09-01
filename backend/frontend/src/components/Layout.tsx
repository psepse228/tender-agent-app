import { useEffect, useRef, useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { motion } from 'motion/react';
import * as api from '../lib/api';
import { useSession } from '../lib/session';
import { useToast } from '../lib/toast';
import { useRefreshControl } from '../lib/refreshControl';
import { getInitData } from '../lib/telegram';
import { BellIcon, ChevronDownIcon, DiamondIcon, LinkIcon, PauseIcon, RefreshIcon, SparkleIcon, ZapIcon } from './icons';

const NAV_TABS = [
  { to: '/', label: 'Тендеры', icon: ZapIcon, end: true },
  { to: '/favorites', label: 'Ваш пакет', icon: SparkleIcon, end: false },
  { to: '/scout', label: 'Скаут AI', icon: DiamondIcon, end: false },
  { to: '/sources', label: 'Источники', icon: LinkIcon, end: false },
];

export default function Layout() {
  return (
    <div>
      <div className="ambient" />
      <SuspendedOverlay />
      <Header />
      <TelegramLinkBanner />
      <div className="screen">
        <Outlet />
      </div>
      <BottomNav />
    </div>
  );
}

function Header() {
  const { email, picture, logout } = useSession();
  const { onRefresh, spinning } = useRefreshControl();
  const [lastUpdate, setLastUpdate] = useState('');
  const [menuOpen, setMenuOpen] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);
  const [loggingOut, setLoggingOut] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Ticks whenever a refresh actually lands -- see Tenders.tsx, which bumps
  // this via the same event the old vanilla frontend's setTime() covered.
  useEffect(() => {
    function onUpdated() {
      const now = new Date();
      setLastUpdate(`${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`);
    }
    window.addEventListener('tenders:updated', onUpdated);
    return () => window.removeEventListener('tenders:updated', onUpdated);
  }, []);

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    }
    document.addEventListener('click', onDocClick);
    return () => document.removeEventListener('click', onDocClick);
  }, []);

  async function handleLogout() {
    setLoggingOut(true);
    setLogoutError(null);
    try {
      await logout();
    } catch (e) {
      setLoggingOut(false);
      setLogoutError(e instanceof Error ? e.message : 'Не удалось выйти');
    }
  }

  return (
    <div className="header">
      <div className="logo">
        <div className="logo-mark">T</div>
        Tender Agent
      </div>
      <div className="header-right">
        {lastUpdate && <div className="last-update">{lastUpdate}</div>}
        {onRefresh && (
          <button className={`refresh-btn${spinning ? ' spinning' : ''}`} onClick={onRefresh} aria-label="Обновить">
            <RefreshIcon />
          </button>
        )}
        {email && (
          <div className="account-menu" ref={menuRef}>
            <button className="account-menu-trigger" onClick={() => setMenuOpen((v) => !v)}>
              <span className="account-menu-avatar">
                {picture ? <img src={picture} alt="" referrerPolicy="no-referrer" /> : email[0]?.toUpperCase()}
              </span>
              <span className="account-menu-chevron">
                <ChevronDownIcon />
              </span>
            </button>
            {menuOpen && (
              <div className="account-menu-dropdown">
                <div className="account-menu-dropdown-email">{email}</div>
                {logoutError && <div className="account-menu-dropdown-error">{logoutError}</div>}
                <button className="account-menu-dropdown-logout" onClick={handleLogout} disabled={loggingOut}>
                  Выйти
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function TelegramLinkBanner() {
  const [show, setShow] = useState(false);
  const { showToast } = useToast();

  useEffect(() => {
    // Only relevant when actually opened inside Telegram -- a plain browser
    // session has no Telegram identity to offer linking at all.
    const initData = getInitData();
    if (!initData) return;
    api
      .getTelegramLinkStatus()
      .then((status) => setShow(!status.linked))
      .catch(() => {}); // best-effort
  }, []);

  async function handleLink() {
    const initData = getInitData();
    if (!initData) return;
    try {
      await api.linkTelegram(initData);
      setShow(false);
      showToast('Telegram подключён для уведомлений');
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Не удалось подключить Telegram');
    }
  }

  if (!show) return null;
  return (
    <div className="telegram-link-banner">
      <span>
        <BellIcon /> Подключи Telegram, чтобы получать уведомления о лучших тендерах сразу
      </span>
      <button onClick={handleLink}>Подключить</button>
    </div>
  );
}

function SuspendedOverlay() {
  const [suspended, setSuspended] = useState(false);

  useEffect(() => {
    // v1 billing -- no payment processor, manually managed by the owner via
    // subscription_status in Supabase. Fail open on any error: a stats
    // endpoint hiccup should never look like a real suspension.
    api
      .getStats()
      .then((data) => setSuspended(data.subscriptionStatus === 'suspended'))
      .catch(() => {});
  }, []);

  if (!suspended) return null;
  return (
    <div className="suspended-overlay">
      <div className="suspended-card">
        <div className="suspended-icon">
          <PauseIcon />
        </div>
        <div className="suspended-title">Подписка приостановлена</div>
        <div className="suspended-text">Свяжитесь с нами, чтобы возобновить доступ к Tender Agent.</div>
      </div>
    </div>
  );
}

function BottomNav() {
  return (
    <div className="bottom-nav">
      {NAV_TABS.map((tab) => (
        <NavLink key={tab.to} to={tab.to} end={tab.end} className={({ isActive }) => `nav-btn${isActive ? ' active' : ''}`}>
          {({ isActive }) => (
            <>
              {isActive && (
                <motion.div
                  layoutId="nav-active-bg"
                  className="nav-btn-active-bg"
                  transition={{ type: 'spring', stiffness: 380, damping: 32 }}
                />
              )}
              <div className="nav-btn-icon">
                <tab.icon />
              </div>
              <div className="nav-btn-label">{tab.label}</div>
            </>
          )}
        </NavLink>
      ))}
    </div>
  );
}
