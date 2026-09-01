// Honest loading placeholders -- replaces the old behaviour of just showing
// a blank cards container (or the global #loader spinner) until data
// arrives, which read as broken on a slow connection.

export function SkeletonCard() {
  return (
    <div className="card" style={{ cursor: 'default' }}>
      <div className="card-top">
        <div className="skeleton" style={{ width: 40, height: 30, borderRadius: 'var(--r-sm)' }} />
        <div className="card-info" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div className="skeleton" style={{ width: '70%', height: 12 }} />
          <div className="skeleton" style={{ width: '45%', height: 10 }} />
        </div>
      </div>
      <div className="skeleton" style={{ width: '100%', height: 2 }} />
    </div>
  );
}

export function SkeletonCards({ count = 4 }: { count?: number }) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </>
  );
}

export function SkeletonStat() {
  return (
    <div className="dash-stat">
      <div className="skeleton" style={{ width: '50%', height: 28, marginBottom: 8 }} />
      <div className="skeleton" style={{ width: '70%', height: 9 }} />
    </div>
  );
}

export function SkeletonChatListItem() {
  return (
    <div className="chat-list-item" style={{ cursor: 'default' }}>
      <div className="skeleton" style={{ width: 42, height: 42, borderRadius: 14, flexShrink: 0 }} />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div className="skeleton" style={{ width: '60%', height: 12 }} />
        <div className="skeleton" style={{ width: '40%', height: 10 }} />
      </div>
    </div>
  );
}
