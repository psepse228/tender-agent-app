import { useEffect, useRef, useState } from 'react';
import type { ChatMessage } from '../lib/types';
import { formatChatTime } from '../lib/format';
import { ArrowRightIcon } from './icons';

interface ChatPanelProps {
  messages: ChatMessage[];
  placeholderMessage: string;
  inputPlaceholder: string;
  sending: boolean;
  onSend: (message: string) => Promise<void>;
}

/** Shared chat UI for Скаут AI (profile chat) and a favorited tender's own
 * Tender AI tab -- same layout, different backing endpoint (see api.ts). */
export function ChatPanel({ messages, placeholderMessage, inputPlaceholder, sending, onSend }: ChatPanelProps) {
  const [value, setValue] = useState('');
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, sending]);

  async function handleSend() {
    const message = value.trim();
    if (!message || sending) return;
    setValue('');
    await onSend(message);
  }

  return (
    <div className="chat-panel">
      <div className="chat-messages" ref={containerRef}>
        {messages.length === 0 ? (
          <ChatBubble role="bot" content={placeholderMessage} />
        ) : (
          messages.map((m, i) => <ChatBubble key={i} role={m.role} content={m.content} timestamp={m.created_at} />)
        )}
        {sending && <TypingBubble />}
      </div>
      <div className="chat-input-row">
        <input
          className="chat-input"
          type="text"
          placeholder={inputPlaceholder}
          value={value}
          disabled={sending}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleSend();
          }}
        />
        <button className="chat-send-btn" onClick={handleSend} disabled={sending || !value.trim()}>
          <ArrowRightIcon />
        </button>
      </div>
    </div>
  );
}

function ChatBubble({ role, content, timestamp }: { role: 'client' | 'bot'; content: string; timestamp?: string | null }) {
  const isClient = role === 'client';
  return (
    <div className={`chat-row ${isClient ? 'client' : 'bot'}`}>
      {!isClient && <div className="chat-avatar">T</div>}
      <div className={`chat-bubble ${isClient ? 'client' : 'bot'}`}>
        <div className="chat-bubble-text">{content}</div>
        <div className="chat-bubble-time">{formatChatTime(timestamp)}</div>
      </div>
    </div>
  );
}

function TypingBubble() {
  return (
    <div className="chat-row bot">
      <div className="chat-avatar">T</div>
      <div className="chat-bubble bot typing">
        <div className="chat-typing-dot" />
        <div className="chat-typing-dot" />
        <div className="chat-typing-dot" />
      </div>
    </div>
  );
}
