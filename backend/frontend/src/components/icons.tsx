// A shared icon set replacing the emoji the previous vanilla frontend used
// (⚡ ✦ ◆ 🔗 💰 📅 ↻ ✕ → ✓ ◎ ⚠ ⓘ 🔔 ⏸ 📈 ▾). Plain inline SVG, sized to
// fill its parent via width="1em" height="1em" so a single fontSize/className
// controls scale everywhere it's used -- nothing to fail to load.

type IconProps = { className?: string };

/** Тендеры tab -- replaces ⚡ */
export function ZapIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="1em" height="1em" className={className} aria-hidden>
      <path d="M13 2 4 14h6l-1 8 9-12h-6l1-8Z" fill="currentColor" />
    </svg>
  );
}

/** Ваш пакет / Tender AI -- replaces ✦ */
export function SparkleIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="1em" height="1em" className={className} aria-hidden>
      <path
        d="M12 2c.6 3.7 1.6 6 3.2 7.7 1.6 1.6 4 2.6 7.8 3.3-3.8.7-6.2 1.7-7.8 3.3-1.6 1.7-2.6 4-3.2 7.7-.6-3.7-1.6-6-3.2-7.7-1.6-1.6-4-2.6-7.8-3.3 3.8-.7 6.2-1.7 7.8-3.3C10.4 8 11.4 5.7 12 2Z"
        fill="currentColor"
      />
    </svg>
  );
}

/** Скаут AI tab -- replaces ◆ */
export function DiamondIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="1em" height="1em" className={className} aria-hidden>
      <path d="M12 2 22 12 12 22 2 12 12 2Z" fill="currentColor" />
    </svg>
  );
}

/** Источники tab / "open tender" link -- replaces 🔗 */
export function LinkIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="1em" height="1em" className={className} fill="none" aria-hidden>
      <path
        d="M9.5 14.5 14.5 9.5M11 7l1.3-1.3a3.5 3.5 0 0 1 5 5L16 12M13 17l-1.3 1.3a3.5 3.5 0 0 1-5-5L8 12"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function RefreshIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="1em" height="1em" className={className} fill="none" aria-hidden>
      <path
        d="M20 11A8 8 0 0 0 6.3 6.3L4 8.6M4 13a8 8 0 0 0 13.7 4.7L20 15.4M4 4v4.6h4.6M19.4 19.4v-4.6h-4.6"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function CloseIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="1em" height="1em" className={className} fill="none" aria-hidden>
      <path d="M5 5l14 14M19 5 5 19" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function ChevronRightIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="1em" height="1em" className={className} fill="none" aria-hidden>
      <path d="M9 5l7 7-7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function ChevronDownIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="1em" height="1em" className={className} fill="none" aria-hidden>
      <path d="M5 9l7 7 7-7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function ArrowRightIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="1em" height="1em" className={className} fill="none" aria-hidden>
      <path d="M4 12h15M13 6l7 6-7 6" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function ArrowLeftIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="1em" height="1em" className={className} fill="none" aria-hidden>
      <path d="M20 12H5M11 6l-7 6 7 6" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function CheckIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="1em" height="1em" className={className} fill="none" aria-hidden>
      <path d="M5 12.5 9.5 17 19 7" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** Empty-state mark -- replaces ◎ */
export function TargetIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="1em" height="1em" className={className} fill="none" aria-hidden>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.6" />
      <circle cx="12" cy="12" r="4.5" stroke="currentColor" strokeWidth="1.6" />
      <circle cx="12" cy="12" r="1" fill="currentColor" />
    </svg>
  );
}

export function AlertTriangleIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="1em" height="1em" className={className} fill="none" aria-hidden>
      <path
        d="M12 3.5 22 20H2L12 3.5Z"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinejoin="round"
      />
      <path d="M12 10v4.5M12 17.3h.01" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" />
    </svg>
  );
}

export function InfoIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="1em" height="1em" className={className} fill="none" aria-hidden>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.6" />
      <path d="M12 11v5.5M12 7.6h.01" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" />
    </svg>
  );
}

export function BellIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="1em" height="1em" className={className} fill="none" aria-hidden>
      <path
        d="M6 10a6 6 0 1 1 12 0c0 4 1.5 5.5 2 6H4c.5-.5 2-2 2-6Z"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinejoin="round"
      />
      <path d="M10 19a2 2 0 0 0 4 0" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  );
}

export function PauseIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="1em" height="1em" className={className} aria-hidden>
      <rect x="6" y="4" width="4.5" height="16" rx="1.5" fill="currentColor" />
      <rect x="13.5" y="4" width="4.5" height="16" rx="1.5" fill="currentColor" />
    </svg>
  );
}

export function TrendingUpIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="1em" height="1em" className={className} fill="none" aria-hidden>
      <path d="M3 17l6-6 4 4 8-8M15 7h6v6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function WalletIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="1em" height="1em" className={className} fill="none" aria-hidden>
      <rect x="3" y="6" width="18" height="13" rx="2.5" stroke="currentColor" strokeWidth="1.7" />
      <path d="M3 10h18" stroke="currentColor" strokeWidth="1.7" />
      <circle cx="16.5" cy="14" r="1.3" fill="currentColor" />
    </svg>
  );
}

export function CalendarIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="1em" height="1em" className={className} fill="none" aria-hidden>
      <rect x="3.5" y="5" width="17" height="16" rx="2.5" stroke="currentColor" strokeWidth="1.7" />
      <path d="M3.5 9.5h17M8 3v3.5M16 3v3.5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  );
}

export function TrashIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="1em" height="1em" className={className} fill="none" aria-hidden>
      <path
        d="M5 7h14M9.5 7V5a1.5 1.5 0 0 1 1.5-1.5h2A1.5 1.5 0 0 1 14.5 5v2M7 7l1 12.5A1.5 1.5 0 0 0 9.5 21h5a1.5 1.5 0 0 0 1.5-1.5L17 7"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function XCircleIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="1em" height="1em" className={className} fill="none" aria-hidden>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.7" />
      <path d="M9.5 9.5l5 5M14.5 9.5l-5 5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  );
}
