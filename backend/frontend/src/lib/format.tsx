/** Score tone bucket, shared by score pills, progress bars and criteria. */
export type ScoreTone = 'high' | 'mid' | 'low';
export function scoreTone(v: number): ScoreTone {
  return v >= 70 ? 'high' : v >= 40 ? 'mid' : 'low';
}

export function criterionColor(v: number): string {
  if (v >= 70) return 'var(--green)';
  if (v >= 40) return 'var(--yellow)';
  return 'var(--red)';
}

// Safety net for older rows / partial AI compliance -- the scoring prompt
// now asks for DD.MM.YYYY directly, but this normalizes anything that
// still comes back as an ISO or English-language date (e.g. "July 15, 2026").
export function formatDeadline(raw: string | undefined): string {
  if (!raw) return '';
  // Already DD.MM.YYYY (the scoring prompt's normal output) -- return as
  // -is. `new Date(raw)` below would otherwise misparse it as US-style
  // MM.DD.YYYY (e.g. "05.09.2026" meant as 5 September silently became 9
  // May), which daysUntilDeadline's own dedicated DD.MM.YYYY parsing never
  // had this bug in, producing a "N days left" figure right next to a
  // wrong date right under it.
  if (/^\d{2}\.\d{2}\.\d{4}/.test(raw)) return raw;
  const iso = /^(\d{4})-(\d{2})-(\d{2})/.exec(raw);
  if (iso) return `${iso[3]}.${iso[2]}.${iso[1]}`;
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return raw;
  return `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}.${d.getFullYear()}`;
}

// Parses either the DD.MM.YYYY the scoring prompt asks for or an ISO/
// English-language fallback (same inputs formatDeadline above handles),
// returning whole days from today (negative once past) -- powers the
// Тендеры feed's "Дедлайн скоро" grouping and the detail page's timeline.
export function daysUntilDeadline(raw: string | undefined): number | null {
  if (!raw) return null;
  let d: Date;
  const dmy = /^(\d{2})\.(\d{2})\.(\d{4})/.exec(raw);
  if (dmy) {
    d = new Date(Number(dmy[3]), Number(dmy[2]) - 1, Number(dmy[1]));
  } else {
    d = new Date(raw);
  }
  if (Number.isNaN(d.getTime())) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  d.setHours(0, 0, 0, 0);
  return Math.round((d.getTime() - today.getTime()) / 86_400_000);
}

export function pluralTenders(n: number): string {
  return `${n} тендер${n === 1 ? '' : n < 5 ? 'а' : 'ов'}`;
}

export type RecommendationTone = 'submit' | 'consider' | 'skip';
export function recommendationTone(r: string | undefined): RecommendationTone {
  if (r?.includes('Подать')) return 'submit';
  if (r?.includes('Рассмотреть')) return 'consider';
  return 'skip';
}

export function formatChatTime(iso?: string | null): string {
  const d = iso ? new Date(iso) : new Date();
  return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
}

export const CHAT_ERROR_MESSAGES: Record<string, string> = {
  'Daily message limit reached, try again tomorrow': 'Дневной лимит сообщений исчерпан, попробуй завтра',
  'Sending messages too quickly, slow down': 'Слишком много сообщений подряд, подожди немного',
};

export function chatErrorMessage(detail: string | undefined): string {
  return (detail && CHAT_ERROR_MESSAGES[detail]) || 'Ошибка при отправке сообщения';
}
