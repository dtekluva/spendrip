import type { Plan } from '../lib/types';

/** Off / 1 / 2 / 3, with a preview of the order it would create. Mirrors engine.set_priority. */
export function insertPriority(order: (number | 'draft')[], id: number | 'draft', rank: number) {
  const next = order.filter((x) => x !== id);
  if (rank > 0) next.splice(Math.min(rank - 1, next.length), 0, id);
  return { order: next.slice(0, 3), dropped: next.slice(3) };
}

export default function RankPicker({ plans, id, current, draftName, onPick }: {
  plans: Plan[]; id: number | 'draft'; current: number; draftName?: string; onPick: (rank: number) => void;
}) {
  const ranked = plans.filter((p) => p.priority_rank).sort((a, b) => a.priority_rank! - b.priority_rank!).map((p) => p.id as number | 'draft');
  const others = ranked.filter((x) => x !== id).length;
  const max = Math.min(3, others + 1);
  const name = (x: number | 'draft') => (x === id ? draftName ?? plans.find((p) => p.id === x)?.label ?? 'This plan' : plans.find((p) => p.id === x)?.label ?? '');
  const { order, dropped } = current ? insertPriority(ranked, id, current) : { order: [], dropped: [] };
  return (
    <>
      <div className="rank-pick" role="group" aria-label="Priority">
        <button aria-pressed={current === 0} onClick={() => onPick(0)}>Off</button>
        {Array.from({ length: max }, (_, i) => i + 1).map((k) => <button key={k} aria-pressed={current === k} onClick={() => onPick(k)}>{k}</button>)}
      </div>
      {current > 0 && <div className="order-preview">{order.map((x, i) => <span key={String(x)} className={x === id ? 'me' : ''}><b>{i + 1}</b> {name(x)}</span>)}</div>}
      {dropped.length > 0 && <p className="small" style={{ color: 'var(--amber)', fontWeight: 700, margin: '6px 0 0' }}>{dropped.map(name).join(', ')} will stop being a priority (max 3).</p>}
    </>
  );
}
