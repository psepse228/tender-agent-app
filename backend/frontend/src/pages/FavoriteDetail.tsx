import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import * as api from '../lib/api';
import { ApiError } from '../lib/api';
import type { ChatMessage } from '../lib/types';
import { chatErrorMessage } from '../lib/format';
import { useFavorites } from '../lib/favorites';
import { useToast } from '../lib/toast';
import { TenderStats, useFavoriteAction } from '../components/TenderStats';
import { ChatPanel } from '../components/ChatPanel';
import { ArrowLeftIcon, SparkleIcon } from '../components/icons';

export default function FavoriteDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { favorites, remove } = useFavorites();
  const { showToast } = useToast();

  const [tab, setTab] = useState<'stats' | 'chat'>('stats');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(true);
  const [sending, setSending] = useState(false);

  const favorite = favorites.find((f) => f.id === id);

  useEffect(() => {
    if (!id) return;
    api
      .getFavoriteChat(id)
      .then((d) => setMessages(d.messages))
      .catch(() => showToast('Ошибка загрузки чата'))
      .finally(() => setChatLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const removeAction = useFavoriteAction(async () => {
    if (!id) return;
    await remove(id);
    showToast('Убрано из Tender AI');
    navigate('/favorites');
  });

  async function handleSend(message: string) {
    if (!id) return;
    setMessages((prev) => [...prev, { role: 'client', content: message }]);
    setSending(true);
    try {
      const { reply } = await api.postFavoriteChat(id, message);
      setMessages((prev) => [...prev, { role: 'bot', content: reply || 'Извините, что-то пошло не так.' }]);
    } catch (e) {
      showToast(e instanceof ApiError ? chatErrorMessage(e.message) : 'Ошибка при отправке сообщения');
    } finally {
      setSending(false);
    }
  }

  if (!favorite) {
    // Not loaded yet (or a stale link) -- favorites always come from the
    // same context Ваш пакет reads, so this only flashes briefly on a
    // direct/refreshed navigation to this URL while it's still fetching.
    return null;
  }

  return (
    // .chat-screen here is just the generic "flex column filling .screen"
    // shell (see index.css) -- header/tabs shrink to content, the active
    // pane is the one flex:1 child, always internally scrolled instead of
    // sometimes-the-page-scrolls/sometimes-the-pane-scrolls depending on
    // which tab happens to be open.
    <div className="chat-screen">
      <div className="fav-detail-header">
        <button className="fav-chat-back press" onClick={() => navigate('/favorites')}>
          <ArrowLeftIcon /> Назад к чатам
        </button>
        <div className="fav-detail-title">{favorite.title || 'Без названия'}</div>
        <div className="fav-detail-org">{favorite.organization || ''}</div>
      </div>

      <div className="detail-tabs">
        <button className={`detail-tab press${tab === 'stats' ? ' active' : ''}`} onClick={() => setTab('stats')}>
          Статистика
        </button>
        <button className={`detail-tab ai-tab press${tab === 'chat' ? ' active' : ''}`} onClick={() => setTab('chat')}>
          <SparkleIcon /> Tender AI
        </button>
      </div>

      {tab === 'stats' ? (
        <div className="sheet-body" style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '16px 16px 40px' }}>
          <TenderStats tender={favorite} isFavorite favoriteBusy={removeAction.busy} onRemoveFavorite={removeAction.run} />
        </div>
      ) : (
        !chatLoading && (
          <ChatPanel
            messages={messages}
            placeholderMessage="Спроси меня что угодно про этот тендер — требования, риски, стоит ли подавать заявку."
            inputPlaceholder="Спроси что-нибудь про этот тендер..."
            sending={sending}
            onSend={handleSend}
          />
        )
      )}
    </div>
  );
}
