import type { CSSProperties } from 'react';
import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFavorites } from '../lib/favorites';
import type { Favorite } from '../lib/types';
import { pluralTenders, recommendationTone, scoreTone } from '../lib/format';
import { SkeletonChatListItem } from '../components/Skeleton';
import { ChevronRightIcon, SparkleIcon } from '../components/icons';

// Was one flat, undifferentiated list -- a tender you saved "to think
// about" and one you're actively preparing a bid for looked identical.
// The backend has no separate "stage" of its own to track that with, but
// it already tells us the AI's own recommendation for each one, so
// grouping by that gives real structure without inventing state that
// isn't actually there yet. See the IA proposal this replaces.
const GROUP_ORDER: { tone: 'submit' | 'consider' | 'skip'; label: string }[] = [
  { tone: 'submit', label: 'Готовить заявку' },
  { tone: 'consider', label: 'На рассмотрении' },
  { tone: 'skip', label: 'Низкий приоритет' },
];

export default function Favorites() {
  const { favorites, loading } = useFavorites();
  const navigate = useNavigate();

  const groups = useMemo(() => {
    const byTone: Record<string, Favorite[]> = { submit: [], consider: [], skip: [] };
    for (const f of favorites) byTone[recommendationTone(f.recommendation)].push(f);
    for (const list of Object.values(byTone)) list.sort((a, b) => (b.matchPercent || 0) - (a.matchPercent || 0));
    return GROUP_ORDER.map((g) => ({ ...g, items: byTone[g.tone] })).filter((g) => g.items.length > 0);
  }, [favorites]);

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
              Пакет пока пуст.
              <br />
              Нажми «+ Пакет» на интересном тендере, чтобы начать.
            </div>
          </div>
        ) : (
          groups.map((group) => (
            <div key={group.tone} className="feed-group">
              <div className="feed-group-label">
                {group.label}
                <span className="feed-group-count">{group.items.length}</span>
              </div>
              {group.items.map((f, i) => {
                const tone = scoreTone(f.matchPercent || 0);
                return (
                  <div
                    key={f.id}
                    role="button"
                    tabIndex={0}
                    className="chat-list-item stagger-item"
                    style={{ '--i': i } as CSSProperties}
                    onClick={() => navigate(`/tenders/${f.id}`)}
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
              })}
            </div>
          ))
        )}
      </div>
    </>
  );
}
