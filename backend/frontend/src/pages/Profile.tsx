import { useEffect, useState, type CSSProperties } from 'react';
import * as api from '../lib/api';
import { ApiError } from '../lib/api';
import type { ChatMessage, Source } from '../lib/types';
import { chatErrorMessage } from '../lib/format';
import { useToast } from '../lib/toast';
import { useSession } from '../lib/session';
import { ChatPanel } from '../components/ChatPanel';
import { LinkIcon, TrashIcon, UserIcon } from '../components/icons';

type Segment = 'company' | 'sources' | 'account' | 'methodology';

const SEGMENTS: { key: Segment; label: string }[] = [
  { key: 'company', label: 'Компания' },
  { key: 'sources', label: 'Источники' },
  { key: 'account', label: 'Аккаунт' },
  { key: 'methodology', label: 'Методология' },
];

/**
 * Everything one-time/setup-shaped lives here now, as sub-sections of one
 * destination, instead of Скаут AI and Источники each holding a permanent
 * bottom-nav slot next to the screens actually used every day. See the IA
 * proposal this replaces.
 */
export default function Profile() {
  const [segment, setSegment] = useState<Segment>('company');

  return (
    <div className="chat-screen">
      <div className="fav-detail-header">
        <div className="fav-detail-title">Профиль</div>
        <div className="fav-detail-org">Компания, источники, аккаунт и методология скоринга</div>
      </div>

      <div className="detail-tabs" style={{ marginBottom: 0 }}>
        {SEGMENTS.map((s) => (
          <button key={s.key} className={`detail-tab press${segment === s.key ? ' active' : ''}`} onClick={() => setSegment(s.key)}>
            {s.label}
          </button>
        ))}
      </div>

      {segment === 'company' && <CompanySegment />}
      {segment === 'sources' && <SourcesSegment />}
      {segment === 'account' && <AccountSegment />}
      {segment === 'methodology' && <MethodologySegment />}
    </div>
  );
}

function CompanySegment() {
  const { showToast } = useToast();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    api
      .getProfileChat()
      .then((d) => setMessages(d.messages))
      .catch(() => showToast('Ошибка загрузки чата'))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSend(message: string) {
    setMessages((prev) => [...prev, { role: 'client', content: message }]);
    setSending(true);
    try {
      const { reply } = await api.postProfileChat(message);
      setMessages((prev) => [...prev, { role: 'bot', content: reply || 'Извините, что-то пошло не так.' }]);
    } catch (e) {
      showToast(e instanceof ApiError ? chatErrorMessage(e.message) : 'Ошибка при отправке сообщения');
    } finally {
      setSending(false);
    }
  }

  if (loading) return null;
  return (
    <ChatPanel
      messages={messages}
      placeholderMessage="Привет! Расскажи о своей компании — чем вы занимаетесь, какой у вас опыт, какие тендеры вам интересны. Это поможет AI точнее находить подходящие тендеры."
      inputPlaceholder="Напиши сообщение..."
      sending={sending}
      onSend={handleSend}
    />
  );
}

function SourcesSegment() {
  const { showToast } = useToast();
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [adding, setAdding] = useState(false);

  function load() {
    api
      .getSources()
      .then(setSources)
      .catch(() => showToast('Ошибка загрузки источников'))
      .finally(() => setLoading(false));
  }
  useEffect(load, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleAdd() {
    const trimmedName = name.trim();
    const trimmedUrl = url.trim();
    if (!trimmedName || !trimmedUrl) {
      showToast('Укажи название и ссылку');
      return;
    }
    if (!trimmedUrl.startsWith('http://') && !trimmedUrl.startsWith('https://')) {
      showToast('Ссылка должна начинаться с http:// или https://');
      return;
    }
    setAdding(true);
    try {
      await api.addSource(trimmedName, trimmedUrl);
      setName('');
      setUrl('');
      showToast('Источник добавлен');
      load();
    } catch {
      showToast('Не удалось добавить источник');
    } finally {
      setAdding(false);
    }
  }

  async function handleRemove(id: string, sourceName: string) {
    if (!window.confirm(`Удалить источник «${sourceName}»?`)) return;
    try {
      await api.removeSource(id);
      setSources((prev) => prev.filter((s) => s.id !== id));
      showToast('Источник удалён');
    } catch {
      showToast('Не удалось удалить источник');
    }
  }

  return (
    <div className="sheet-body" style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '16px 16px 40px' }}>
      <p className="profile-sub" style={{ marginBottom: 14 }}>
        Добавь свои сайты с тендерами — они будут проверяться вместе с остальными при каждом обновлении
      </p>
      <input className="chat-input" type="text" placeholder="Название (напр. Мой сайт тендеров)" value={name} onChange={(e) => setName(e.target.value)} />
      <input className="chat-input" type="text" placeholder="https://..." style={{ marginTop: 8 }} value={url} onChange={(e) => setUrl(e.target.value)} />
      <button className="favorite-btn press" style={{ marginTop: 10 }} onClick={handleAdd} disabled={adding}>
        + Добавить источник
      </button>

      <div className="cards" style={{ padding: 0, marginTop: 20 }}>
        {!loading &&
          (sources.length === 0 ? (
            <div className="empty" style={{ display: 'flex', width: '100%' }}>
              <div className="empty-icon">
                <LinkIcon />
              </div>
              <div className="empty-text">
                Пока нет добавленных источников.
                <br />
                Используются только 7 стандартных площадок.
              </div>
            </div>
          ) : (
            sources.map((s, i) => (
              <div className="source-item stagger-item" style={{ '--i': i } as CSSProperties} key={s.id}>
                <div className="source-item-info">
                  <div className="source-item-name">{s.name}</div>
                  <div className="source-item-url">{s.url}</div>
                </div>
                <button className="source-item-remove press" onClick={() => handleRemove(s.id, s.name)}>
                  <TrashIcon />
                </button>
              </div>
            ))
          ))}
      </div>
    </div>
  );
}

function AccountSegment() {
  const { email, picture, logout } = useSession();
  const [subscriptionStatus, setSubscriptionStatus] = useState<string | null>(null);
  const [loggingOut, setLoggingOut] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getStats()
      .then((d) => setSubscriptionStatus(d.subscriptionStatus ?? null))
      .catch(() => {});
  }, []);

  async function handleLogout() {
    setLoggingOut(true);
    setError(null);
    try {
      await logout();
    } catch (e) {
      setLoggingOut(false);
      setError(e instanceof Error ? e.message : 'Не удалось выйти');
    }
  }

  return (
    <div className="sheet-body" style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '16px 16px 40px' }}>
      <div className="account-card">
        <span className="account-menu-avatar" style={{ width: 44, height: 44, fontSize: 17 }}>
          {picture ? <img src={picture} alt="" referrerPolicy="no-referrer" /> : email ? email[0]?.toUpperCase() : <UserIcon />}
        </span>
        <div>
          <div className="account-card-email">{email || 'Не авторизован'}</div>
          {subscriptionStatus && (
            <div className={`account-card-status${subscriptionStatus === 'suspended' ? ' suspended' : ''}`}>
              {subscriptionStatus === 'suspended' ? 'Подписка приостановлена' : 'Подписка активна'}
            </div>
          )}
        </div>
      </div>
      {error && <div className="account-menu-dropdown-error" style={{ marginTop: 12 }}>{error}</div>}
      <button className="favorite-btn remove press" style={{ marginTop: 16 }} onClick={handleLogout} disabled={loggingOut}>
        Выйти
      </button>
    </div>
  );
}

function MethodologySegment() {
  return (
    <div className="method-body" style={{ flex: 1, minHeight: 0, overflowY: 'auto' }}>
      <p className="method-intro">
        Оценка не строится на догадках. Мы используем признанные международные методики bid/proposal management — те же
        принципы, на которых десятилетиями строится профессиональная оценка тендеров в крупных консалтинговых и подрядных
        компаниях.
      </p>

      <div className="method-section">
        <h4>Три вопроса, на которые отвечает оценка</h4>
        <p>
          Для каждого тендера ИИ по сути отвечает на три вопроса, лежащих в основе методики go/no-go от Shipley Associates:
          тендер реален (бюджет и сроки достижимы)? он выигрываем (у компании есть реальная конкурентная позиция)? и стоит
          ли он усилий (соответствие и потенциальная выгода оправдывают участие)?
        </p>
      </div>

      <div className="method-section">
        <h4>Из чего складывается итоговый балл</h4>
        <p>
          <b>Соответствие (40%)</b> — совпадает ли предмет тендера с реальными услугами компании, а не только с бюджетом или
          именем заказчика.
        </p>
        <p>
          <b>Финансы (20%)</b> — реалистичность и достаточность бюджета тендера.
        </p>
        <p>
          <b>Реализация (25%)</b> — сможет ли компания реально выполнить проект: сроки, масштаб, ресурсы.
        </p>
        <p>
          <b>Шанс победы (15%)</b> — конкурентная позиция: сертификаты, опыт по теме, насколько узкий или открытый конкурс.
        </p>
        <div className="method-formula">Итог = Соответствие×0.4 + Финансы×0.2 + Реализация×0.25 + Шанс×0.15</div>
        <p>70%+ — «Подать заявку», 40–69% — «Рассмотреть», ниже 40% — «Пропустить».</p>
      </div>

      <div className="method-section">
        <h4>Почему это не просто ИИ-угадайка</h4>
        <p>
          Каждая оценка регулярно проверяется на реальных сценариях — включая заведомо нерелевантные тендеры (например,
          IT-проект для компании без опыта в IT), чтобы ИИ честно занижал оценку вместо того, чтобы искать повод «подойдёт
          для развития компетенций». Это тестируется на реальной модели, а не только на заранее заготовленных ответах.
        </p>
      </div>

      <div className="method-sources">
        Методология опирается на: Shipley Associates (капчур-менеджмент и go/no-go анализ), APMP — Association of Proposal
        Management Professionals (стандарты индустрии), и PWin (Probability of Win) — анализ вероятности победы, применяемый
        в госзакупках и крупном b2b-тендеринге.
      </div>
    </div>
  );
}
