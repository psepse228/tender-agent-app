import { useCallback, useMemo, useState, type CSSProperties } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'motion/react';
import { ApiError } from '../lib/api';
import type { Tender } from '../lib/types';
import { daysUntilDeadline, formatDeadline, pluralTenders, recommendationTone, scoreTone } from '../lib/format';
import { useFavorites } from '../lib/favorites';
import { useTenders } from '../lib/tenders';
import { useToast } from '../lib/toast';
import { useRegisterRefreshControl } from '../lib/refreshControl';
import { SkeletonCards, SkeletonStat } from '../components/Skeleton';
import { CountUp } from '../components/CountUp';
import { CalendarIcon, ChevronRightIcon, ClockIcon, InfoIcon, SparkleIcon, TargetIcon, WalletIcon } from '../components/icons';

// Was 4 flat filter chips over one undifferentiated list -- now the list
// itself is pre-sorted into groups by what actually makes a tender worth
// looking at first, and the chips just narrow which groups show. See the
// IA proposal this replaces: a feed with priority, not a list + filters.
type Filter = 'all' | 'high' | 'submit';
const FILTERS: { key: Filter; label: string }[] = [
  { key: 'all', label: 'Все' },
  { key: 'high', label: '≥70%' },
  { key: 'submit', label: 'Подать' },
];

const URGENT_DAYS = 7;

function recTagClass(t: Tender): string {
  const tone = recommendationTone(t.recommendation);
  return tone === 'submit' ? 'tag-submit' : tone === 'consider' ? 'tag-consider' : 'tag-skip';
}
function recTagLabel(t: Tender): string {
  const tone = recommendationTone(t.recommendation);
  return tone === 'submit' ? 'Подать заявку' : tone === 'consider' ? 'Рассмотреть' : 'Пропустить';
}

export default function Tenders() {
  const navigate = useNavigate();
  const { showToast } = useToast();
  const favorites = useFavorites();
  const { tenders, loading, needsProfile, refresh } = useTenders();

  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState<Filter>('all');

  const handleRefresh = useCallback(async () => {
    if (refreshing) return;
    setRefreshing(true);
    showToast('Ищем тендеры... (1-2 мин)', 130000);
    try {
      const result = await refresh();
      if (!result) return;
      const suffix = result.failed.length ? ` · ${result.failed.join(', ')} ${result.failed.length > 1 ? 'недоступны' : 'недоступен'}` : '';
      showToast(result.found > 0 ? `Найдено ${result.found} тендеров${suffix}` : `Новых тендеров не найдено${suffix}`);
    } catch (e) {
      showToast(e instanceof ApiError && e.status === 429 ? 'Обновлялось недавно, попробуй чуть позже' : 'Ошибка при обновлении');
    } finally {
      setRefreshing(false);
    }
  }, [refreshing, refresh, showToast]);

  useRegisterRefreshControl(handleRefresh, refreshing);

  const filtered = useMemo(() => {
    let f = [...tenders];
    if (filter === 'high') f = f.filter((t) => (t.matchPercent || 0) >= 70);
    if (filter === 'submit') f = f.filter((t) => (t.recommendation || '').includes('Подать'));
    return f;
  }, [tenders, filter]);

  const groups = useMemo(() => {
    const urgent: Tender[] = [];
    const high: Tender[] = [];
    const rest: Tender[] = [];
    for (const t of filtered) {
      const days = daysUntilDeadline(t.deadline);
      if (days !== null && days >= 0 && days <= URGENT_DAYS) urgent.push(t);
      else if ((t.matchPercent || 0) >= 70) high.push(t);
      else rest.push(t);
    }
    const byScore = (a: Tender, b: Tender) => (b.matchPercent || 0) - (a.matchPercent || 0);
    urgent.sort((a, b) => (daysUntilDeadline(a.deadline) ?? 99) - (daysUntilDeadline(b.deadline) ?? 99));
    high.sort(byScore);
    rest.sort(byScore);
    return [
      { key: 'urgent', label: 'Дедлайн скоро', icon: ClockIcon, items: urgent },
      { key: 'high', label: 'Высокий балл', icon: SparkleIcon, items: high },
      { key: 'rest', label: 'Остальное', icon: null, items: rest },
    ].filter((g) => g.items.length > 0);
  }, [filtered]);

  const avg = tenders.length ? Math.round(tenders.reduce((s, t) => s + (t.matchPercent || 0), 0) / tenders.length) : 0;
  const submitCount = tenders.filter((t) => (t.recommendation || '').includes('Подать')).length;

  async function handleToggleFavorite(t: Tender, favoriteId: string | undefined) {
    try {
      if (favoriteId) {
        await favorites.remove(favoriteId);
        showToast('Убрано из Пакета');
      } else {
        const { alreadyExisted } = await favorites.add(t.id);
        showToast(alreadyExisted ? 'Уже добавлено в Пакет' : 'Добавлено в Пакет');
      }
    } catch {
      showToast(favoriteId ? 'Не удалось убрать из Пакета' : 'Не удалось добавить в Пакет');
    }
  }

  let cardIndex = 0;

  return (
    <>
      <div className="dashboard">
        <div className="dash-eyebrow">
          Обзор · сегодня
          <button className="dash-eyebrow-link press" onClick={() => navigate('/methodology')}>
            <InfoIcon /> Как считается
          </button>
        </div>
        <div className="dash-stats">
          {loading ? (
            <>
              <SkeletonStat />
              <SkeletonStat />
              <SkeletonStat />
            </>
          ) : (
            <>
              <div className="dash-stat accent stagger-item" style={{ '--i': 0 } as CSSProperties}>
                <CountUp value={tenders.length} className="dash-num plain" />
                <div className="dash-label2">Найдено</div>
              </div>
              <div className="dash-stat stagger-item" style={{ '--i': 1 } as CSSProperties}>
                <CountUp value={submitCount} className="dash-num green-num" />
                <div className="dash-label2">К подаче</div>
              </div>
              <div className="dash-stat stagger-item" style={{ '--i': 2 } as CSSProperties}>
                <CountUp value={avg} suffix="%" className="dash-num" />
                <div className="dash-label2">Ср. балл</div>
              </div>
            </>
          )}
        </div>
      </div>

      <div className="filters-wrap">
        <div className="filters">
          {FILTERS.map((f) => (
            <button key={f.key} className={`filter-btn press${filter === f.key ? ' active' : ''}`} onClick={() => setFilter(f.key)}>
              {f.label}
            </button>
          ))}
        </div>
        {!loading && <div className="count-badge">{pluralTenders(filtered.length)}</div>}
      </div>

      <div className="cards">
        {loading ? (
          <SkeletonCards />
        ) : filtered.length === 0 ? (
          <div className="empty" style={{ display: 'flex', width: '100%' }}>
            <div className="empty-icon">
              <TargetIcon />
            </div>
            {needsProfile && tenders.length === 0 ? (
              <button className="empty-action empty-text press" onClick={() => navigate('/profile')}>
                Сначала настрой профиль компании — это поможет AI точнее находить тендеры.
                <br />
                Затем нажми ↻ чтобы запустить поиск.
              </button>
            ) : (
              <div className="empty-text">
                Тендеров не найдено.
                <br />
                Нажми ↻ чтобы запустить поиск.
              </div>
            )}
          </div>
        ) : (
          groups.map((group) => (
            <div key={group.key} className="feed-group">
              <div className="feed-group-label">
                {group.icon && <group.icon />}
                {group.label}
                <span className="feed-group-count">{group.items.length}</span>
              </div>
              {group.items.map((t) => {
                const tone = scoreTone(t.matchPercent || 0);
                const fav = favorites.findFor(t);
                const i = cardIndex++;
                return (
                  <motion.div
                    key={t.id}
                    role="button"
                    tabIndex={0}
                    className={`card ${tone}`}
                    onClick={() => navigate(`/tenders/${t.id}`)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') navigate(`/tenders/${t.id}`);
                    }}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.28, delay: Math.min(i * 0.04, 0.4) }}
                  >
                    <div className="card-top">
                      <div className={`card-score-pill ${tone}`}>{t.matchPercent || 0}</div>
                      <div className="card-info">
                        <div className="card-title">{t.title || 'Без названия'}</div>
                        <div className="card-org">{t.organization || '—'}</div>
                        <div className="card-tags">
                          <span className={`tag ${recTagClass(t)}`}>{recTagLabel(t)}</span>
                          {t.budget && (
                            <span className="tag tag-meta">
                              <WalletIcon /> {t.budget}
                            </span>
                          )}
                          {t.deadline && (
                            <span className="tag tag-meta">
                              <CalendarIcon /> до {formatDeadline(t.deadline)}
                            </span>
                          )}
                        </div>
                      </div>
                      <button
                        type="button"
                        className={`card-fav-btn press${fav ? ' active' : ''}`}
                        title={fav ? 'Убрать из Пакета' : 'Добавить в Пакет'}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleToggleFavorite(t, fav?.id);
                        }}
                      >
                        {fav ? (
                          <>
                            <SparkleIcon /> В пакете
                          </>
                        ) : (
                          '+ Пакет'
                        )}
                      </button>
                      <div className="card-chevron">
                        <ChevronRightIcon />
                      </div>
                    </div>
                    <div className="card-bar">
                      <div className="card-bar-fill" style={{ width: `${t.matchPercent || 0}%` }} />
                    </div>
                  </motion.div>
                );
              })}
            </div>
          ))
        )}
      </div>
    </>
  );
}
