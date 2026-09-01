// Shared "stats" markup for the tender detail page's Обзор tab. Split into
// content (this) + a separately-pinned TenderActions footer (see below) --
// the decision buttons used to be the last thing at the bottom of a long
// scroll, behind the score/criteria/AI-analysis text, which put them
// outside the thumb zone exactly when someone had already read enough to
// decide. Now they're always reachable without scrolling.
import { useState } from 'react';
import type { Tender } from '../lib/types';
import { criterionColor, formatDeadline, recommendationTone, scoreTone } from '../lib/format';
import { openLink } from '../lib/telegram';
import { AlertTriangleIcon, ArrowRightIcon, CalendarIcon, CheckIcon, LinkIcon, SparkleIcon, WalletIcon, XCircleIcon } from './icons';

const CRITERIA_META = [
  { key: 'compliance' as const, name: 'Соответствие', weight: '×0.4' },
  { key: 'financial' as const, name: 'Финансы', weight: '×0.2' },
  { key: 'feasibility' as const, name: 'Реализация', weight: '×0.25' },
  { key: 'winChance' as const, name: 'Шанс победы', weight: '×0.15' },
];

function VerdictLine({ recommendation }: { recommendation: string | undefined }) {
  const tone = recommendationTone(recommendation);
  const Icon = tone === 'submit' ? CheckIcon : tone === 'consider' ? SparkleIcon : XCircleIcon;
  const label = tone === 'submit' ? 'Подать заявку' : tone === 'consider' ? 'Рассмотреть' : 'Пропустить';
  const cls = tone === 'submit' ? 'high' : tone === 'consider' ? 'mid' : 'low';
  return (
    <div className={`verdict-line ${cls}`}>
      <Icon /> {label}
    </div>
  );
}

interface TenderStatsProps {
  tender: Tender;
}

export function TenderStats({ tender: t }: TenderStatsProps) {
  const pct = t.matchPercent || 0;
  const tone = scoreTone(pct);

  return (
    <>
      <div className="sheet-score-row">
        <div className={`sheet-score-pill ${tone}`}>
          <div className={`sheet-score-num ${tone}`}>{pct}</div>
        </div>
        <div>
          <div className="sheet-title">{t.title || ''}</div>
          <div className="sheet-org">{t.organization || ''}</div>
          {/* The one fact this whole screen exists to deliver -- promoted
              next to the score instead of buried as a small badge below
              the fold, and shown once instead of duplicated as both a tag
              and a badge the way it used to be. */}
          <VerdictLine recommendation={t.recommendation} />
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
        {CRITERIA_META.map((c) => {
          const val = t[c.key] || 0;
          const col = criterionColor(val);
          return (
            <div className="criterion" key={c.key}>
              <div className="criterion-top">
                <span className="criterion-name">
                  {c.name} <span className="criterion-weight">{c.weight}</span>
                </span>
                <span className="criterion-val" style={{ color: col }}>
                  {val}%
                </span>
              </div>
              <div className="criterion-track">
                <div className="criterion-fill" style={{ width: `${val}%`, background: col }} />
              </div>
            </div>
          );
        })}
      </div>

      <div className="sheet-sections">
        {/* Risk is the one block that genuinely needs a "pay attention"
            color -- why-participate and the action plan are supporting
            context, not warnings, so they read as calmer/neutral now
            instead of competing with risk for the same visual urgency
            (three saturated colors on one screen was diluting all three). */}
        {t.whyParticipate && (
          <div className="ai-block neutral">
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
          <div className="ai-block neutral">
            <div className="ai-block-label">
              <ArrowRightIcon /> План действий
            </div>
            <div className="ai-block-text">{t.actionPlan}</div>
          </div>
        )}
        {!t.whyParticipate && !t.risks && !t.actionPlan && t.reasoning && (
          <div className="ai-block neutral">
            <div className="ai-block-label">AI Анализ</div>
            <div className="ai-block-text">{t.reasoning}</div>
          </div>
        )}
      </div>

      {(t.riskLevel || t.profitPotential) && (
        <div className="sheet-badges">
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
      )}
    </>
  );
}

interface TenderActionsProps {
  tender: Tender;
  isFavorite: boolean;
  favoriteBusy?: boolean;
  onAddFavorite?: () => void;
  onRemoveFavorite?: () => void;
}

/** The two decisions this whole page exists to support -- pinned outside
 * the scrolling content (see TenderDetail.tsx) so they're reachable from
 * anywhere in the read, not just after scrolling past everything else. */
export function TenderActions({ tender: t, isFavorite, favoriteBusy, onAddFavorite, onRemoveFavorite }: TenderActionsProps) {
  const fullSource = t.source && t.source.startsWith('http') ? t.source : '';
  return (
    <div className="detail-actions-bar">
      {fullSource ? (
        <button className="open-tender-btn press" onClick={() => openLink(fullSource)}>
          <LinkIcon /> Открыть тендер
        </button>
      ) : (
        <button className="open-tender-btn disabled" disabled>
          Ссылка недоступна
        </button>
      )}

      {isFavorite ? (
        <button className="favorite-btn remove press" onClick={onRemoveFavorite} disabled={favoriteBusy}>
          <XCircleIcon /> Убрать
        </button>
      ) : (
        <button className="favorite-btn press" onClick={onAddFavorite} disabled={favoriteBusy}>
          <SparkleIcon /> В пакет
        </button>
      )}
    </div>
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
