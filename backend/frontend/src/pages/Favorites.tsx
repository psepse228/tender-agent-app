import type { CSSProperties } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFavorites } from '../lib/favorites';
import { pluralTenders, scoreTone } from '../lib/format';
import { SkeletonChatListItem } from '../components/Skeleton';
import { ChevronRightIcon, SparkleIcon } from '../components/icons';

// TODO(frontend-rewrite): this is a working port of the vanilla "Ваш пакет"
// chat-list screen, not yet polished with motion/empty-state parity the way
// Tenders.tsx is -- next screen in the rewrite queue.
export default function Favorites() {
  const { favorites, loading } = useFavorites();
  const navigate = useNavigate();

  return (
    <>
      <div className="dashboard">
        <div className="dash-eyebrow">Ваш пакет</div>
      </div>
      <div className="filters-wrap">
        <div />
        {!loading && <div className="count-badge">{pluralTenders(favorites.length)}</div>}
      </div>
      <div className="cards">
        {loading ? (
          <>
            <SkeletonChatListItem />
            <SkeletonChatListItem />
          </>
        ) : favorites.length === 0 ? (
          <div className="empty" style={{ display: 'flex', width: '100%' }}>
            <div className="empty-icon">
              <SparkleIcon />
            </div>
            <div className="empty-text">
              Пока нет чатов с Tender AI.
              <br />
              Нажми «+ AI» на интересном тендере, чтобы начать.
            </div>
          </div>
        ) : (
          favorites.map((f, i) => {
            const tone = scoreTone(f.matchPercent || 0);
            return (
              <div
                key={f.id}
                role="button"
                tabIndex={0}
                className="chat-list-item stagger-item"
                style={{ '--i': i } as CSSProperties}
                onClick={() => navigate(`/favorites/${f.id}`)}
              >
                <div className={`chat-list-avatar ${tone}`}>{f.matchPercent || 0}</div>
                <div className="chat-list-body">
                  <div className="chat-list-name">{f.title || 'Без названия'}</div>
                  <div className="chat-list-preview">
                    <span className="ai-tag">
                      <SparkleIcon /> Tender AI
                    </span>
                    {f.organization || 'Нажми, чтобы обсудить'}
                  </div>
                </div>
                <div className="card-chevron">
                  <ChevronRightIcon />
                </div>
              </div>
            );
          })
        )}
      </div>
    </>
  );
}
