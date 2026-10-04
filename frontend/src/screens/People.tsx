import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { N } from '../lib/format';
import { useStore } from '../lib/store';
import type { Plan, Recipient } from '../lib/types';
import { AddRecipient } from './NewPlan';
import Kobo from '../components/Kobo';

/** Plans that pay this person: their own single plans, plus any group they're on. */
export function plansFor(r: Recipient, plans: Plan[]) {
  return plans.filter((p) => p.state !== 'finished' && (p.recipient?.id === r.id || (p.lines ?? []).some((l) => l.recipient.id === r.id)));
}

export const personColour = (r: Recipient) => (r.is_self ? 'cobalt' : (['hibiscus', 'mint', 'sun', 'cobalt'] as const)[r.id % 4]);

export default function People() {
  const { recipients, plans, reload, toast, openSheet, closeSheet } = useStore();
  const nav = useNavigate();
  const [err, setErr] = useState('');
  const people = recipients.filter((r) => !r.label.endsWith('(removed)')).sort((a, b) => Number(b.is_self) - Number(a.is_self) || a.label.localeCompare(b.label));
  const add = () => openSheet(<AddRecipient onSaved={() => { closeSheet(); }} />);
  const remove = async (r: Recipient) => {
    setErr('');
    try { await api.del(`/recipients/${r.id}`); await reload(); toast(`${r.label} removed`); closeSheet(); } catch (e: any) { setErr(e.message); closeSheet(); }
  };
  const open = (r: Recipient) => {
    const using = plansFor(r, plans);
    const monthly = using.reduce((t, p) => t + (p.kind === 'group' ? (p.lines?.find((l) => l.recipient.id === r.id)?.amount_kobo ?? 0) : p.amount_kobo), 0);
    openSheet(
      <>
        <div style={{ display: 'flex', gap: 14, alignItems: 'center', marginBottom: 12 }}>
          <span className={`tile t-${personColour(r)}`}>{r.is_self ? '🙋' : r.label[0]}</span>
          <div><h3 style={{ margin: 0 }}>{r.label}</h3><div className="muted small">{r.verified_account_name} · {r.bank_name} ••{r.account_last4}</div></div>
        </div>
        <div className="kv"><span className="muted">WhatsApp when money lands</span><b>{r.is_self ? 'Not needed' : r.whatsapp ? (r.notify_whatsapp ? 'On' : 'Off') : 'No number'}</b></div>
        <div className="kv" style={{ marginTop: 6 }}><span className="muted">Plans paying {r.is_self ? 'you' : 'them'}</span><b>{using.length}{using.length ? ` · ${N(monthly)} per drip in all` : ''}</b></div>
        {using.length > 0 && (
          <div className="opt-list" style={{ marginTop: 12 }}>
            {using.map((p) => (
              <button key={p.id} className="opt" onClick={() => { closeSheet(); nav(`/plans?open=${p.id}`); }}>
                <span className={`tile sm t-${p.tint}`}>{p.emoji}</span>
                <span><b>{p.label}</b><br /><span className="small muted">{p.kind === 'group' ? `${N(p.lines?.find((l) => l.recipient.id === r.id)?.amount_kobo ?? 0)} in a group of ${p.lines?.length}` : N(p.amount_kobo)}{p.status === 'paused' ? ' · paused' : ''}</span></span>
                <span className="small muted">›</span>
              </button>
            ))}
          </div>
        )}
        <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
          <button className="btn btn-primary" style={{ flex: 1 }} onClick={() => { closeSheet(); nav(`/plans/new?to=${r.id}`); }}>New plan for {r.is_self ? 'me' : r.label}</button>
          {!r.is_self && !using.length && <button className="btn btn-soft" style={{ color: 'var(--red)' }} onClick={() => remove(r)}>Remove</button>}
        </div>
        {!r.is_self && using.length > 0 && <p className="small muted" style={{ margin: '10px 0 0' }}>To remove {r.label}, first change or delete the plans that pay them.</p>}
      </>,
    );
  };
  return (
    <div className="stack">
      <div className="cols cols-act"><div className="col stack">
        <div><div className="eyebrow">{people.length} {people.length === 1 ? 'person' : 'people'}</div><h1 className="h1">People you pay</h1></div>
        {err && <div className="error-card">{err}</div>}
        <div className="list">
          {people.map((r) => {
            const n = plansFor(r, plans).length;
            return (
              <button key={r.id} className="set-row" onClick={() => open(r)}>
                <span className={`tile sm t-${personColour(r)}`}>{r.is_self ? '🙋' : r.label[0]}</span>
                <span style={{ minWidth: 0 }}><b>{r.label}{r.is_self ? ' (you)' : ''}</b>
                  <span className="sub">{r.verified_account_name} · {r.bank_name} ••{r.account_last4} · {n ? `${n} plan${n === 1 ? '' : 's'}` : 'no plans yet'}{r.whatsapp && r.notify_whatsapp ? ' · WhatsApp on' : ''}</span></span>
              </button>
            );
          })}
        </div>
        {!people.length && <div className="card kobo-empty"><Kobo mood="peek" size={64} /><span className="muted">Nobody yet. Add the first person you want to pay.</span></div>}
        <button className="btn btn-primary btn-block" onClick={add}>＋ Add someone</button>
      </div><div className="col stack">
        <div className="card act-sum">
          <div className="eyebrow">Good to know</div>
          <p className="small muted" style={{ margin: 0 }}>Every account is name-checked with the bank before it's saved, and money only ever goes to people on this list.</p>
          <p className="small muted" style={{ margin: 0 }}>Add a WhatsApp number and they get a message the moment money lands, so no more "have you sent it?".</p>
        </div>
      </div></div>
    </div>
  );
}
