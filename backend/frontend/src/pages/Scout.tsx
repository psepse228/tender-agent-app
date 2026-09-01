import { useEffect, useState } from 'react';
import * as api from '../lib/api';
import { ApiError } from '../lib/api';
import type { ChatMessage } from '../lib/types';
import { chatErrorMessage } from '../lib/format';
import { useToast } from '../lib/toast';
import { ChatPanel } from '../components/ChatPanel';

export default function Scout() {
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

  return (
    <div className="chat-screen">
      <div className="chat-header">
        <div className="chat-eyebrow">AI · Профиль компании</div>
        <div className="profile-title">Скаут AI</div>
        <div className="profile-sub">
          Здесь вы настраиваете поиск тендеров: расскажите о компании, и Скаут AI составит профиль, по которому подбираются
          подходящие тендеры.
        </div>
      </div>
      {!loading && (
        <ChatPanel
          messages={messages}
          placeholderMessage="Привет! Расскажи о своей компании — чем вы занимаетесь, какой у вас опыт, какие тендеры вам интересны. Это поможет AI точнее находить подходящие тендеры."
          inputPlaceholder="Напиши сообщение..."
          sending={sending}
          onSend={handleSend}
        />
      )}
    </div>
  );
}
