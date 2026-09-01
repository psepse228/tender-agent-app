import { useCallback, useEffect, useMemo, useState, type CSSProperties } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'motion/react';
import * as api from '../lib/api';
import { ApiError } from '../lib/api';
import type { Tender } from '../lib/types';
import { formatDeadline, pluralTenders, recommendationTone, scoreTone } from '../lib/format';
import { useFavorites } from '../lib/favorites';
import { useToast } from '../lib/toast';
import { useRegisterRefreshControl } from '../lib/refreshControl';
import { BottomSheet } from '../components/BottomSheet';
import { TenderStats, useFavoriteAction } from '../components/TenderStats';
import { SkeletonCards, SkeletonStat } from '../components/Skeleton';
import { CountUp } from '../components/CountUp';
import { CalendarIcon, ChevronRightIcon, InfoIcon, SparkleIcon, TargetIcon, WalletIcon } from '../components/icons';

type Filter = 'all' | 'high' | 'submit' | 'consider';

const FILTERS: { key: Filter; label: string }[] = [
  { key: 'all', label: 'Все' },
  { key: 'high', label: '≥70%' },
  { key: 'submit', label: 'Подать' },
  { key: 'consider', label: 'Рассмотреть' },
];

const DEFAULT_EMPTY_TEXT = (
  <>
    Тендеров не найдено.
    <br />
    Нажми ↻ чтобы запустить поиск.
  </>
);
const NUDGE_EMPTY_TEXT = (
  <>
    Сначала настрой профиль компании — это поможет AI точнее находить тендеры.
    <br />
    Затем нажми ↻ чтобы запустить поиск.
  </>
);

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

  const [tenders, setTenders] = useState<Tender[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState<Filter>('all');
  const [selected, setSelected] = useState<Tender | null>(null);
  const [needsProfile, setNeedsProfile] = useState(false);

  const loadTenders = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getTenders();
      setTenders(data);
      window.dispatchEvent(new Event('tenders:updated'));
      if (data.length === 0) {
        const profile = await api.getProfile().catch(() => ({ profile_text: '' }));
        setNeedsProfile(!profile.profile_text);
      } else {
        setNeedsProfile(false);
      }
    } catch {
      showToast('Ошибка загрузки');
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    loadTenders();
  }, [loadTenders]);

  const handleRefresh = useCallback(async () => {
    if (refreshing) return;
    setRefreshing(true);
    showToast('Ищем тендеры... (1-2 мин)', 130000);

    const progressTimer = setInterval(async () => {
      try {
        const { total, done, sources } = await api.getRefreshStatus();
        if (!done) return;
        const failed = sources.filter((s) => s.status === 'failed').map((s) => s.name);
        const suffix = failed.length ? ` · ${failed.join(', ')} недоступен` : '';
        showToast(`Проверено ${done} из ${total} источников...${suffix}`, 130000);
      } catch {
        /* progress is best-effort; ignore polling errors */
      }
    }, 2000);

    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 100000);
    try {
      const { tenders: fresh, sourcesStatus } = await api.refreshTenders(ctrl.signal);
      const failedSources = sourcesStatus.filter((s) => s.status === 'failed');
      const suffix = failedSources.length
        ? ` · ${failedSources.map((s) => s.name).join(', ')} ${failedSources.length > 1 ? 'недоступны' : 'недоступен'}`
        : '';
      if (fresh.length > 0) {
        setTenders(fresh);
        window.dispatchEvent(new Event('tenders:updated'));
        showToast(`Найдено ${fresh.length} тендеров${suffix}`);
      } else {
        showToast(`Новых тендеров не найдено${suffix}`);
      }
    } catch (e) {
      if (e instanceof ApiError && e.status === 429) {
        showToast('Обновлялось недавно, попробуй чуть позже');
      } else if (e instanceof DOMException && e.name === 'AbortError') {
        showToast('Превышено время ожидания');
      } else {
        showToast('Ошибка при обновлении');
      }
    } finally {
      clearTimeout(timer);
      clearInterval(progressTimer);
      setRefreshing(false);
    }
  }, [refreshing, showToast]);

  useRegisterRefreshControl(handleRefresh, refreshing);

  const filtered = useMemo(() => {
    let f = [...tenders];
    if (filter === 'high') f = f.filter((t) => (t.matchPercent || 0) >= 70);
    if (filter === 'submit') f = f.filter((t) => (t.recommendation || '').includes('Подать'));
    if (filter === 'consider') f = f.filter((t) => (t.recommendation || '').includes('Рассмотреть'));
    return f.sort((a, b) => (b.matchPercent || 0) - (a.matchPercent || 0));
  }, [tenders, filter]);

  const avg = tenders.length ? Math.round(tenders.reduce((s, t) => s + (t.matchPercent || 0), 0) / tenders.length) : 0;
  const submitCount = tenders.filter((t) => (t.recommendation || '').includes('Подать')).length;

  async function handleToggleFavorite(t: Tender, favoriteId: string | undefined) {
    try {
      if (favoriteId) {
        await favorites.remove(favoriteId);
        showToast('Убрано из Tender AI');
      } else {
        const { alreadyExisted } = await favorites.add(t.id);
        showToast(alreadyExisted ? 'Уже добавлено в Tender AI' : 'Добавлено в Tender AI');
      }
    } catch {
      showToast(favoriteId ? 'Не удалось убрать из Tender AI' : 'Не удалось добавить в Tender AI');
    }
  }

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
              <button className="empty-action empty-text press" onClick={() => navigate('/scout')}>
                {NUDGE_EMPTY_TEXT}
              </button>
            ) : (
              <div className="empty-text">{DEFAULT_EMPTY_TEXT}</div>
            )}
          </div>
        ) : (
          filtered.map((t, i) => {
            const tone = scoreTone(t.matchPercent || 0);
            const fav = favorites.findFor(t);
            return (
              <motion.div
                key={t.id}
                role="button"
                tabIndex={0}
                className={`card ${tone}`}
                onClick={() => setSelected(t)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') setSelected(t);
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
                    title={fav ? 'Убрать из Tender AI' : 'Добавить в Tender AI'}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleToggleFavorite(t, fav?.id);
                    }}
                  >
                    {fav ? (
                      <>
                        <SparkleIcon /> AI
                      </>
                    ) : (
                      '+ AI'
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
          })
        )}
      </div>

      <BottomSheet open={!!selected} onClose={() => setSelected(null)}>
        {selected && <TenderSheetBody tender={selected} />}
      </BottomSheet>
    </>
  );
}

/** Wired to the live favorites context so the sheet's own add/remove button
 * (and the underlying tender's "+ AI" card button) always agree. */
function TenderSheetBody({ tender }: { tender: Tender }) {
  const favorites = useFavorites();
  const { showToast } = useToast();
  const fav = favorites.findFor(tender);

  const addAction = useFavoriteAction(async () => {
    const { alreadyExisted } = await favorites.add(tender.id);
    showToast(alreadyExisted ? 'Уже добавлено в Tender AI' : 'Добавлено в Tender AI');
  });
  const removeAction = useFavoriteAction(async () => {
    if (!fav) return;
    await favorites.remove(fav.id);
    showToast('Убрано из Tender AI');
  });

  return (
    <TenderStats
      tender={tender}
      isFavorite={!!fav}
      favoriteBusy={addAction.busy || removeAction.busy}
      onAddFavorite={addAction.run}
      onRemoveFavorite={removeAction.run}
    />
  );
}
