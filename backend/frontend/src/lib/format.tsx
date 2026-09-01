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
  const iso = /^(\d{4})-(\d{2})-(\d{2})/.exec(raw);
  if (iso) return `${iso[3]}.${iso[2]}.${iso[1]}`;
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return raw;
  return `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}.${d.getFullYear()}`;
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
