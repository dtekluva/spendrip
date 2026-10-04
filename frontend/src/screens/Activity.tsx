import { useEffect, useState } from 'react';
import { useFillHeight } from '../lib/fill';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { dayLabel, fmtTime, N } from '../lib/format';
import type { ActivityItem } from '../lib/types';
import { StatusPill, useAction } from '../components/ui';
import { useStore } from '../lib/store';
import Kobo from '../components/Kobo';

const GROUP_REASON: Record<string, string> = {
  protected_for_priorities: 'Waited to keep your priorities safe. Nobody was paid.', insufficient_funds: "Your balance couldn't cover everyone, so nobody was paid.",
  daily_cap: 'It would have gone over your daily limit, so nobody was paid.', paused: 'It was paused.', missed: 'It was too late to send it that day.',
};

/** A group payout: one row with the total, opening to show each person. */
function GroupRow({ a, onRetried }: { a: ActivityItem; onRetried: () => void }) {
  const nav = useNavigate();
  const { toast, koboSay } = useStore();
  const { busy, error, run } = useAction();
  const people = a.people ?? [];
  const n = people.length;
  const title = a.status === 'sent' ? `${a.plan!.label}: all ${n} paid` : a.status === 'partial' ? `${a.plan!.label}: ${a.paid} of ${n} paid`
    : a.status === 'sending' ? `${a.plan!.label} is sending to ${n} people` : `${a.plan!.label} (${n} people) ${a.status === 'waited' ? 'waited' : a.status === 'missed' ? 'was missed' : 'was paused'}`;
  const out = a.status === 'sent' || a.status === 'partial' || a.status === 'sending';
  const unpaid = people.filter((p) => p.status !== 'sent').length;
  const canRetry = !a.retried && a.status !== 'sending' && unpaid > 0;
  const retry = () => run(async () => {
    const r = await api.post<{ people: number; amount_kobo: number }>(`/payouts/${a.id}/retry`, {});
    koboSay('fill', `Sending again to ${r.people} ${r.people === 1 ? 'person' : 'people'} (${N(r.amount_kobo)}). Watch Activity.`);
    onRetried();
  }).catch((e: any) => toast(e.message));
  return (
    <details className="act act-group">
      <summary>
        <span className={`ic t-${a.plan!.tint}`}>{a.plan!.emoji}</span>
        <div style={{ minWidth: 0 }}><b>{title}</b><div className="small muted">{out ? `${n} people · tap to see each` : GROUP_REASON[a.reason ?? ''] ?? 'Nobody was paid.'} · {fmtTime(a.at)}</div>
          {a.status === 'waited' && <button className="link small" style={{ marginTop: 6 }} onClick={() => nav('/fund')}>Top up</button>}</div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
          <b className="num" style={!out ? { color: 'var(--muted)' } : undefined}>{out ? '−' : ''}{N(out ? a.amount_kobo : people.reduce((t, p) => t + p.amount_kobo, 0))}</b>
          {out && !!a.fee_kobo && <span className="small muted num">+ {N(a.fee_kobo)} fees</span>}
          <StatusPill status={a.status === 'partial' ? 'failed' : a.status} />
        </div>
      </summary>
      <div className="g-people">
        {people.map((p, j) => (
          <div key={j} className="kv sub"><span className="muted">{p.label} · {p.bank_name} ••{p.account_last4}</span>
            <span className="num" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>{N(p.amount_kobo)} <StatusPill status={p.status} /></span></div>
        ))}
        {a.status === 'partial' && <p className="small muted" style={{ margin: '6px 0 0' }}>Money for the transfers that didn't go through is back in your balance. Check their account details in the plan.</p>}
        {a.is_retry && <p className="small muted" style={{ margin: '6px 0 0' }}>This was a "send again" of an earlier payout.</p>}
        {a.retried && <p className="small muted" style={{ margin: '6px 0 0' }}>Sent again: see the newer payout above.</p>}
        {canRetry && (
          <button className="btn btn-primary" style={{ marginTop: 10 }} disabled={busy} onClick={retry}>
            {busy ? 'Starting…' : `Send again to ${unpaid} ${unpaid === 1 ? 'person' : 'people'}`}
          </button>
        )}
        {error && <div className="error-card" style={{ marginTop: 8 }}>{error}</div>}
      </div>
    </details>
  );
}

const REASON: Record<string, string> = {
  protected_for_priorities: 'Waited to keep your priorities safe.', insufficient_funds: 'Waited because your balance was too low.',
  daily_cap: 'Waited because it would go over your daily limit.',
};

export default function Activity() {
  const nav = useNavigate();
  const [items, setItems] = useState<ActivityItem[] | null>(null);
  const [filter, setFilter] = useState<'all' | 'money' | 'msg'>('all');
  const [showAll, setShowAll] = useState(false);  // phones: 10 items, then View more; wide screens scroll the list in its own box
  useEffect(() => { api.get<ActivityItem[]>('/activity').then(setItems); }, []);
  const listRef = useFillHeight<HTMLDivElement>(0, 240, items !== null);
  if (!items) return <div className="stack"><div className="skeleton" /><div className="skeleton" /></div>;

  const shown = items.filter((a) => filter === 'all' || (filter === 'money' ? a.status !== 'waited' : !!a.whatsapp));
  const sum = (s: string) => items.filter((a) => a.status === s || (s === 'sent' && a.status === 'partial')).reduce((t, a) => t + a.amount_kobo, 0);
  let last = '';
  return (
    <div className="stack">
      <div><div className="eyebrow">Everything that happened</div><h1 className="h1">Activity</h1></div>
      <div className="cols cols-act"><div className="col stack">
        <div className="seg" role="group" aria-label="Filter">
          {([['all', 'All'], ['money', 'Money'], ['msg', 'Messages']] as const).map(([k, l]) => <button key={k} aria-pressed={filter === k} onClick={() => setFilter(k)}>{l}</button>)}
        </div>
        <div className={`act-list ${showAll ? 'expanded' : ''}`} ref={listRef}>
        {shown.map((a, i) => {
          const lbl = dayLabel(a.at); const head = lbl !== last ? <div className="day-h">{lbl}</div> : null; last = lbl;
          const extra = i >= 10 ? 'extra' : '';
          if (a.kind === 'group') return <div key={i} className={extra}>{head}<GroupRow a={a} onRetried={() => api.get<ActivityItem[]>('/activity').then(setItems)} /></div>;
          const isIn = a.kind === 'inflow';
          const title = isIn ? `${N(a.amount_kobo)} added` : `${a.plan!.label} ${({ sent: 'sent', waited: 'waited', failed: "didn't go through", missed: 'was missed', sending: 'is sending', paused: 'was paused' } as Record<string, string>)[a.status] ?? a.status}`;
          const sub = isIn ? (a.sender && /top-up$/i.test(a.sender) ? a.sender : `Bank transfer${a.sender ? ` from ${a.sender}` : ''}`) : a.status === 'waited' ? REASON[a.reason ?? ''] ?? 'Waited for a top-up.' : `To ${a.recipient!.label} · ${a.recipient!.bank_name} ••${a.recipient!.account_last4}`;
          const sign = isIn ? '+' : a.status === 'sent' || a.status === 'sending' ? '−' : '';
          return (
            <div key={i} className={extra}>
              {head}
              <div className="act">
                <span className={`ic t-${isIn ? 'mint' : a.plan!.tint}`}>{isIn ? '⬇️' : a.plan!.emoji}</span>
                <div style={{ minWidth: 0 }}><b>{title}</b><div className="small muted">{sub} · {fmtTime(a.at)}</div>
                  {a.whatsapp && <div className="wa"><div className="wa-h">WhatsApp to {a.whatsapp.to}{a.whatsapp.status === 'mocked' ? ' · preview (not sent yet)' : ''}</div>{a.whatsapp.body}</div>}
                  {(a.status === 'sent' || a.status === 'sending') && !!a.fee_lines?.length && (
                    <div className="small muted num fee-inline">{a.fee_lines.map((l) => `${l.label} ${N(l.amount_kobo)}`).join(' · ')}</div>
                  )}
                  {a.status === 'waited' && <button className="link small" style={{ marginTop: 6 }} onClick={() => nav('/fund')}>Top up</button>}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
                  <b className="num" style={a.status === 'waited' ? { color: 'var(--muted)' } : undefined}>{sign}{N(a.amount_kobo)}</b>
                  {(a.status === 'sent' || a.status === 'sending') && !!a.fee_kobo && (
                    <span className="small muted num" title={(a.fee_lines ?? []).map((l) => `${l.label} ${N(l.amount_kobo)}`).join(' · ')}>+ {N(a.fee_kobo)} fees</span>
                  )}
                  <StatusPill status={a.status} />
                </div>
              </div>
            </div>
          );
        })}
        {shown.length > 10 && (
          <button className="act more" onClick={() => setShowAll((v) => !v)} aria-expanded={showAll}>
            {showAll ? 'Show fewer' : `View ${shown.length - 10} more`}</button>
        )}
        </div>
        {!shown.length && <div className="card kobo-empty"><Kobo mood="peek" size={64} follow /><span className="muted">Nothing here yet. Your first drip will show up here.</span></div>}
      </div><div className="col stack">
        <div className="card act-sum">
          <div className="eyebrow">Recent</div>
          <div className="kv"><span className="muted">Sent</span><b className="num">{N(sum('sent'))}</b></div>
          <div className="kv"><span className="muted">Added</span><b className="num">{N(sum('received'))}</b></div>
          <div className="kv"><span className="muted">Waited for top-up</span><b className="num">{items.filter((a) => a.status === 'waited').length}</b></div>
          <div className="kv"><span className="muted">WhatsApp messages</span><b className="num">{items.filter((a) => a.whatsapp).length}</b></div>
        </div>
      </div></div>
    </div>
  );
}
