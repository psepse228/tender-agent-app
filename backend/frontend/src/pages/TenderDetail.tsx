import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import * as api from '../lib/api';
import { ApiError } from '../lib/api';
import type { ChatMessage, Tender } from '../lib/types';
import { chatErrorMessage, daysUntilDeadline, formatDeadline, scoreTone } from '../lib/format';
import { useFavorites } from '../lib/favorites';
import { useTenders } from '../lib/tenders';
import { useToast } from '../lib/toast';
import { TenderActions, TenderStats, useFavoriteAction } from '../components/TenderStats';
import { ChatPanel } from '../components/ChatPanel';
import { ArrowLeftIcon, BuildingIcon, ChevronRightIcon, ClockIcon, SparkleIcon } from '../components/icons';

type Tab = 'overview' | 'similar' | 'chat';

/**
 * One detail page reached from both Тендеры (by the raw tender id, not
 * favorited yet) and Пакет (by the favorite row's id) -- previously two
 * different UIs (a bottom sheet with static text, and a separate favorite
 * page with its own near-duplicate stats markup) for what is, to the
 * person using it, the same thing: "everything about this tender". See
 * the IA proposal this replaces.
 */
export default function TenderDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const { tenders, fromSameOrg } = useTenders();
  const favorites = useFavorites();

  const [tab, setTab] = useState<Tab>('overview');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [preparingChat, setPreparingChat] = useState(false);
  const [sending, setSending] = useState(false);

  // Resolve the tender two ways: `id` might be a favorite row's own id
  // (arrived from Пакет) or a raw tender id (arrived from the Тендеры
  // feed, possibly not favorited at all yet).
  const favoriteMatch = favorites.favorites.find((f) => f.id === id);
  const tenderMatch = tenders.find((t) => t.id === id);
  const tender: Tender | undefined = favoriteMatch ?? tenderMatch;
  const existingFavorite = favoriteMatch ?? (tenderMatch ? favorites.findFor(tenderMatch) : undefined);
  const [favoriteId, setFavoriteId] = useState<string | undefined>(existingFavorite?.id);

  useEffect(() => {
    setFavoriteId(existingFavorite?.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [existingFavorite?.id]);

  const similar = useMemo(() => (tender ? fromSameOrg(tender).slice(0, 5) : []), [tender, fromSameOrg]);
  const days = tender ? daysUntilDeadline(tender.deadline) : null;

  const addAction = useFavoriteAction(async () => {
    if (!tender) return;
    const { alreadyExisted } = await favorites.add(tender.id);
    showToast(alreadyExisted ? 'Уже добавлено в Пакет' : 'Добавлено в Пакет');
  });
  const removeAction = useFavoriteAction(async () => {
    if (!favoriteId) return;
    await favorites.remove(favoriteId);
    showToast('Убрано из Пакета');
  });

  // Loads the chat once we actually have a favorite to hang it off of --
  // and if the person opens the Tender AI tab on a tender they haven't
  // saved yet, this quietly saves it first instead of making "add to
  // Пакет" a mandatory separate step before they can ask a question.
  async function openChatTab() {
    setTab('chat');
    if (favoriteId) {
      if (messages.length === 0) loadChat(favoriteId);
      return;
    }
    if (!tender) return;
    setPreparingChat(true);
    try {
      const { favoriteId: newId } = await favorites.add(tender.id);
      setFavoriteId(newId);
      loadChat(newId);
    } catch {
      showToast('Не удалось подготовить чат');
      setTab('overview');
    } finally {
      setPreparingChat(false);
    }
  }

  function loadChat(fid: string) {
    setChatLoading(true);
    api
      .getFavoriteChat(fid)
      .then((d) => setMessages(d.messages))
      .catch(() => showToast('Ошибка загрузки чата'))
      .finally(() => setChatLoading(false));
  }

  async function handleSend(message: string) {
    if (!favoriteId) return;
    setMessages((prev) => [...prev, { role: 'client', content: message }]);
    setSending(true);
    try {
      const { reply } = await api.postFavoriteChat(favoriteId, message);
      setMessages((prev) => [...prev, { role: 'bot', content: reply || 'Извините, что-то пошло не так.' }]);
    } catch (e) {
      showToast(e instanceof ApiError ? chatErrorMessage(e.message) : 'Ошибка при отправке сообщения');
    } finally {
      setSending(false);
    }
  }

  if (!tender) {
    // Ids are re-minted on every refresh (see the backend's own scraping
    // pipeline) -- a link opened after a background refresh, or a direct
    // reload, can legitimately point at nothing anymore.
    return (
      <div className="chat-screen">
        <div className="fav-detail-header">
          <button className="fav-chat-back press" onClick={() => navigate(-1)}>
            <ArrowLeftIcon /> Назад
          </button>
        </div>
        <div className="empty" style={{ display: 'flex', flex: 1 }}>
          <div className="empty-text">Этот тендер больше не в списке — возможно, список обновился.</div>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-screen">
      <div className="fav-detail-header">
        <button className="fav-chat-back press" onClick={() => navigate(-1)}>
          <ArrowLeftIcon /> Назад
        </button>
        <div className="fav-detail-title">{tender.title || 'Без названия'}</div>
        <div className="fav-detail-org">{tender.organization || ''}</div>
      </div>

      <div className="detail-tabs">
        <button className={`detail-tab press${tab === 'overview' ? ' active' : ''}`} onClick={() => setTab('overview')}>
          Обзор
        </button>
        <button className={`detail-tab press${tab === 'similar' ? ' active' : ''}`} onClick={() => setTab('similar')}>
          Похожие{similar.length > 0 ? ` (${similar.length})` : ''}
        </button>
        <button className={`detail-tab ai-tab press${tab === 'chat' ? ' active' : ''}`} onClick={openChatTab}>
          <SparkleIcon /> Tender AI
        </button>
      </div>

      {tab === 'overview' && (
        <>
          <div className="sheet-body" style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '16px 16px 12px' }}>
            {days !== null && (
              <div className="timeline-row">
                <ClockIcon />
                {days < 0 ? 'Срок подачи истёк' : days === 0 ? 'Дедлайн сегодня' : `Осталось ${days} дн. до ${formatDeadline(tender.deadline)}`}
              </div>
            )}
            <TenderStats tender={tender} />
          </div>
          <TenderActions
            tender={tender}
            isFavorite={!!favoriteId}
            favoriteBusy={addAction.busy || removeAction.busy}
            onAddFavorite={addAction.run}
            onRemoveFavorite={removeAction.run}
          />
        </>
      )}

      {tab === 'similar' && (
        <div className="sheet-body" style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '16px 16px 40px' }}>
          {similar.length === 0 ? (
            <div className="empty" style={{ display: 'flex' }}>
              <div className="empty-icon">
                <BuildingIcon />
              </div>
              <div className="empty-text">
                Среди сейчас загруженных тендеров больше нет других от «{tender.organization || 'этого заказчика'}».
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <p className="profile-sub" style={{ marginBottom: 4 }}>
                Другие тендеры от «{tender.organization}» среди уже найденных:
              </p>
              {similar.map((s) => {
                const tone = scoreTone(s.matchPercent || 0);
                return (
                  <div key={s.id} role="button" tabIndex={0} className="card" onClick={() => navigate(`/tenders/${s.id}`)}>
                    <div className="card-top">
                      <div className={`card-score-pill ${tone}`}>{s.matchPercent || 0}</div>
                      <div className="card-info">
                        <div className="card-title">{s.title || 'Без названия'}</div>
                        <div className="card-org">{s.budget || '—'}</div>
                      </div>
                      <div className="card-chevron">
                        <ChevronRightIcon />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {tab === 'chat' &&
        (preparingChat || chatLoading ? (
          <div className="empty" style={{ display: 'flex', flex: 1 }}>
            <div className="empty-text">Готовим чат…</div>
          </div>
        ) : (
          <ChatPanel
            messages={messages}
            placeholderMessage="Спроси меня что угодно про этот тендер — требования, риски, стоит ли подавать заявку."
            inputPlaceholder="Спроси что-нибудь про этот тендер..."
            sending={sending}
            onSend={handleSend}
          />
        ))}
    </div>
  );
}
