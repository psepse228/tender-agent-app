import { useEffect, useState } from 'react';
import * as api from '../lib/api';
import type { Source } from '../lib/types';
import { useToast } from '../lib/toast';
import { LinkIcon, TrashIcon } from '../components/icons';

export default function Sources() {
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

  async function handleRemove(id: string, name: string) {
    if (!window.confirm(`Удалить источник «${name}»?`)) return;
    try {
      await api.removeSource(id);
      setSources((prev) => prev.filter((s) => s.id !== id));
      showToast('Источник удалён');
    } catch {
      showToast('Не удалось удалить источник');
    }
  }

  return (
    <>
      <div className="dashboard">
        <div className="dash-eyebrow">Источники</div>
        <p className="profile-sub" style={{ marginBottom: 16 }}>
          Добавь свои сайты с тендерами — они будут проверяться вместе с остальными при каждом обновлении
        </p>
      </div>

      <div className="source-form">
        <input
          className="chat-input"
          type="text"
          placeholder="Название (напр. Мой сайт тендеров)"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <input
          className="chat-input"
          type="text"
          placeholder="https://..."
          style={{ marginTop: 8 }}
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
        <button className="favorite-btn" style={{ marginTop: 10 }} onClick={handleAdd} disabled={adding}>
          + Добавить источник
        </button>
      </div>

      <div className="cards" style={{ marginTop: 20 }}>
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
            sources.map((s) => (
              <div className="source-item" key={s.id}>
                <div className="source-item-info">
                  <div className="source-item-name">{s.name}</div>
                  <div className="source-item-url">{s.url}</div>
                </div>
                <button className="source-item-remove" onClick={() => handleRemove(s.id, s.name)}>
                  <TrashIcon />
                </button>
              </div>
            ))
          ))}
      </div>
    </>
  );
}
