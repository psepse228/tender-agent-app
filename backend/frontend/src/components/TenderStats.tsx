// Shared "stats" markup -- used by both the Тендеры bottom sheet and the
// Ваш пакет detail screen's Статистика tab (mirrors renderStatsHtml() in
// the old vanilla frontend).
import { useState } from 'react';
import type { Tender } from '../lib/types';
import { criterionColor, formatDeadline, scoreTone } from '../lib/format';
import { openLink } from '../lib/telegram';
import {
  AlertTriangleIcon,
  ArrowRightIcon,
  CalendarIcon,
  CheckIcon,
  LinkIcon,
  SparkleIcon,
  WalletIcon,
  XCircleIcon,
} from './icons';

function RecommendationBadge({ recommendation }: { recommendation: string | undefined }) {
  if (!recommendation) return null;
  if (recommendation.includes('Подать'))
    return (
      <span className="badge badge-submit">
        <CheckIcon /> Подать заявку
      </span>
    );
  if (recommendation.includes('Рассмотреть'))
    return (
      <span className="badge badge-consider">
        <SparkleIcon /> Рассмотреть
      </span>
    );
  return (
    <span className="badge badge-skip">
      <XCircleIcon /> Пропустить
    </span>
  );
}

interface TenderStatsProps {
  tender: Tender;
  isFavorite: boolean;
  favoriteBusy?: boolean;
  onAddFavorite?: () => void;
  onRemoveFavorite?: () => void;
}

export function TenderStats({ tender: t, isFavorite, favoriteBusy, onAddFavorite, onRemoveFavorite }: TenderStatsProps) {
  const pct = t.matchPercent || 0;
  const tone = scoreTone(pct);
  const fullSource = t.source && t.source.startsWith('http') ? t.source : '';
  const criteria = [
    { name: 'Соответствие', val: t.compliance || 0 },
    { name: 'Финансы', val: t.financial || 0 },
    { name: 'Реализация', val: t.feasibility || 0 },
    { name: 'Шанс победы', val: t.winChance || 0 },
  ];

  return (
    <>
      <div className="sheet-score-row">
        <div className={`sheet-score-pill ${tone}`}>
          <div className={`sheet-score-num ${tone}`}>{pct}</div>
        </div>
        <div>
          <div className="sheet-title">{t.title || ''}</div>
          <div className="sheet-org">{t.organization || ''}</div>
        </div>
      </div>

      {(t.budget || t.deadline) && (
        <div className="sheet-meta">
          {t.budget && (
            <span className="sheet-meta-tag">
              <WalletIcon /> {t.budget}
            </span>
          )}
          {t.deadline && (
            <span className="sheet-meta-tag">
              <CalendarIcon /> {formatDeadline(t.deadline)}
            </span>
          )}
        </div>
      )}

      <div className="sheet-criteria">
        {criteria.map((c) => {
          const col = criterionColor(c.val);
          return (
            <div className="criterion" key={c.name}>
              <div className="criterion-top">
                <span className="criterion-name">{c.name}</span>
                <span className="criterion-val" style={{ color: col }}>
                  {c.val}%
                </span>
              </div>
              <div className="criterion-track">
                <div className="criterion-fill" style={{ width: `${c.val}%`, background: col }} />
              </div>
            </div>
          );
        })}
      </div>

      <div className="sheet-sections">
        {t.whyParticipate && (
          <div className="ai-block why">
            <div className="ai-block-label">
              <CheckIcon /> Почему участвовать
            </div>
            <div className="ai-block-text">{t.whyParticipate}</div>
          </div>
        )}
        {t.risks && (
          <div className="ai-block risk">
            <div className="ai-block-label">
              <AlertTriangleIcon /> Риски
            </div>
            <div className="ai-block-text">{t.risks}</div>
          </div>
        )}
        {t.actionPlan && (
          <div className="ai-block plan">
            <div className="ai-block-label">
              <ArrowRightIcon /> План действий
            </div>
            <div className="ai-block-text">{t.actionPlan}</div>
          </div>
        )}
        {!t.whyParticipate && !t.risks && !t.actionPlan && t.reasoning && (
          <div className="ai-block plan">
            <div className="ai-block-label">AI Анализ</div>
            <div className="ai-block-text">{t.reasoning}</div>
          </div>
        )}
      </div>

      <div className="sheet-badges">
        <RecommendationBadge recommendation={t.recommendation} />
        {t.riskLevel && (
          <span className="badge badge-risk">
            <AlertTriangleIcon /> {t.riskLevel}
          </span>
        )}
        {t.profitPotential && (
          <span className="badge badge-profit">
            <ArrowRightIcon /> {t.profitPotential}
          </span>
        )}
      </div>

      {fullSource ? (
        <button className="open-tender-btn" onClick={() => openLink(fullSource)}>
          <LinkIcon /> Открыть тендер
        </button>
      ) : (
        <button className="open-tender-btn disabled" disabled>
          Ссылка недоступна
        </button>
      )}

      {isFavorite ? (
        <button className="favorite-btn remove press" onClick={onRemoveFavorite} disabled={favoriteBusy}>
          <XCircleIcon /> Убрать из Пакета
        </button>
      ) : (
        <button className="favorite-btn press" onClick={onAddFavorite} disabled={favoriteBusy}>
          <SparkleIcon /> Добавить в Пакет
        </button>
      )}
    </>
  );
}

/** Local busy flag so a slow add/remove request can't be fired twice from
 * the same panel while still letting the parent own the actual favorite
 * state (TenderDetail wires this to its own context calls). */
export function useFavoriteAction(action: () => Promise<void>) {
  const [busy, setBusy] = useState(false);
  return {
    busy,
    run: async () => {
      if (busy) return;
      setBusy(true);
      try {
        await action();
      } finally {
        setBusy(false);
      }
    },
  };
}
