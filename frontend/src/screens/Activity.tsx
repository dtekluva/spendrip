import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { dayLabel, fmtTime, N } from '../lib/format';
import type { ActivityItem } from '../lib/types';
import { StatusPill } from '../components/ui';
import Kobo from '../components/Kobo';

const REASON: Record<string, string> = {
  protected_for_priorities: 'Waited to keep your priorities safe.', insufficient_funds: 'Waited because your balance was too low.',
  daily_cap: 'Waited because it would go over your daily limit.',
};

export default function Activity() {
  const nav = useNavigate();
  const [items, setItems] = useState<ActivityItem[] | null>(null);
  const [filter, setFilter] = useState<'all' | 'money' | 'msg'>('all');
  useEffect(() => { api.get<ActivityItem[]>('/activity').then(setItems); }, []);
  if (!items) return <div className="stack"><div className="skeleton" /><div className="skeleton" /></div>;

  const shown = items.filter((a) => filter === 'all' || (filter === 'money' ? a.status !== 'waited' : !!a.whatsapp));
  const sum = (s: string) => items.filter((a) => a.status === s).reduce((t, a) => t + a.amount_kobo, 0);
  let last = '';
  return (
    <div className="stack">
      <div><div className="eyebrow">Everything that happened</div><h1 className="h1">Activity</h1></div>
      <div className="cols cols-act"><div className="col stack">
        <div className="seg" role="group" aria-label="Filter">
          {([['all', 'All'], ['money', 'Money'], ['msg', 'Messages']] as const).map(([k, l]) => <button key={k} aria-pressed={filter === k} onClick={() => setFilter(k)}>{l}</button>)}
        </div>
        {shown.map((a, i) => {
          const lbl = dayLabel(a.at); const head = lbl !== last ? <div className="day-h">{lbl}</div> : null; last = lbl;
          const isIn = a.kind === 'inflow';
          const title = isIn ? `${N(a.amount_kobo)} added` : `${a.plan!.label} ${({ sent: 'sent', waited: 'waited', failed: "didn't go through", missed: 'was missed', sending: 'is sending', paused: 'was paused' } as Record<string, string>)[a.status] ?? a.status}`;
          const sub = isIn ? `Bank transfer${a.sender ? ` from ${a.sender}` : ''}` : a.status === 'waited' ? REASON[a.reason ?? ''] ?? 'Waited for a top-up.' : `To ${a.recipient!.label} · ${a.recipient!.bank_name} ••${a.recipient!.account_last4}`;
          const sign = isIn ? '+' : a.status === 'sent' || a.status === 'sending' ? '−' : '';
          return (
            <div key={i}>
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
