import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { N } from '../lib/format';
import { useStore } from '../lib/store';
import Kobo from '../components/Kobo';
import { PinDots, PinPad, Switch, useAction } from '../components/ui';
import { cardLabel, type SavedCard } from './CardTopUp';

export interface AutoFillState {
  enabled: boolean; active: boolean; paused_reason: string; card: SavedCard | null;
  payday_end: boolean; payday_start: boolean; just_in_time: boolean;
  max_per_charge_kobo: number | null; max_per_month_kobo: number | null; consent_text: string; skip_window: string;
  next: { at: string; window: string | null; covers_until: string | null; amount_kobo: number; fee_kobo: number; limited_by: string } | null;
  suggested: { month_need_kobo: number; max_per_charge_kobo: number; max_per_month_kobo: number };
  used_this_month_kobo: number; fees_last_30_days_kobo: number;
  history: { at: string; kind: 'payday' | 'jit'; status: 'success' | 'failed'; amount_kobo: number; fee_kobo: number; reason: string }[];
}

const PAUSED: Record<string, string> = {
  card_removed: 'The card was removed.',
  card_expired: 'The card has expired.',
  card_needs_otp: 'Your bank asks for a code on every charge, so this card can’t be charged automatically. Pick another card.',
  declines: 'Your card was declined several times in a row.',
};

const day = (iso: string) => new Date(iso).toLocaleDateString('en-NG', { weekday: 'short', day: 'numeric', month: 'short' });
const time = (iso: string) => new Date(iso).toLocaleTimeString('en-NG', { hour: 'numeric', minute: '2-digit', hour12: true }).replace(' ', ' ').toLowerCase();

export default function AutoFill() {
  const nav = useNavigate();
  const [s, setS] = useState<AutoFillState | null>(null);
  const [cards, setCards] = useState<SavedCard[] | null>(null);
  const [editing, setEditing] = useState(false);
  const load = async () => { const [a, c] = await Promise.all([api.get<AutoFillState>('/autofill'), api.get<SavedCard[]>('/cards')]); setS(a); setCards(c); };
  useEffect(() => { load(); }, []);
  if (!s || !cards) return <div className="stack"><div className="skeleton" /></div>;
  const on = s.active;
  return (
    <div className="stack">
      <div className="close-row"><button className="link" onClick={() => nav(-1)}>← Back</button><span className="eyebrow">Auto-fill</span></div>
      <div><div className="eyebrow">Automatic top-up from your card</div>
        <h1 className="h1">{on ? 'Auto-fill is on' : s.paused_reason ? 'Auto-fill is paused' : 'Never top up by hand again'}</h1></div>
      {!s.enabled && <div className="error-card">Auto-fill is switched off for everyone for now. Your settings are kept.</div>}
      {s.paused_reason && <div className="error-card">{PAUSED[s.paused_reason] ?? 'Auto-fill stopped.'} Check your card and turn it back on below.</div>}
      <div className="cols cols-profile"><div className="col stack">
        {on && !editing ? <Status s={s} onChange={setS} onEdit={() => setEditing(true)} /> : (
          cards.length ? <Setup s={s} cards={cards} onSaved={(a) => { setS(a); setEditing(false); }} onCancel={on ? () => setEditing(false) : undefined} /> : <NoCard />
        )}
      </div><div className="col stack">
        <Explainer />
        {s.history.length > 0 && <History s={s} />}
      </div></div>
    </div>
  );
}

function NoCard() {
  const nav = useNavigate();
  return (
    <div className="card stack" style={{ gap: 10 }}>
      <b>First, save a card</b>
      <p className="small muted" style={{ margin: 0 }}>Auto-fill charges a card you've saved. Top up once with “Save this card” ticked, even ₦100, then come back here.</p>
      <button className="btn btn-primary" onClick={() => nav('/fund')}>Add money and save a card</button>
    </div>
  );
}

function Explainer() {
  return (
    <div className="card act-sum">
      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}><Kobo mood="fill" size={56} /><b>How Auto-fill works</b></div>
      <p className="small muted" style={{ margin: 0 }}><b>Payday fill.</b> On the payday days you choose, we add what your drips need until the next payday, in one charge. We message you that morning, and you can skip it.</p>
      <p className="small muted" style={{ margin: 0 }}><b>Before a drip.</b> If a drip is due within a day and your balance can't cover it, we add just what's missing, once. If the card is declined, we tell you so you can top up.</p>
      <p className="small muted" style={{ margin: 0 }}>Paystack's card fee applies to each charge (1.5%, plus ₦100 from ₦2,500, never more than ₦2,000). One payday charge a month is the cheapest way. There's no SpenDrip fee for Auto-fill.</p>
    </div>
  );
}

function Status({ s, onChange, onEdit }: { s: AutoFillState; onChange: (a: AutoFillState) => void; onEdit: () => void }) {
  const { reload, toast, openSheet, closeSheet, koboSay } = useStore();
  const { busy, error, run } = useAction();
  const n = s.next;
  const skipped = !!n?.window && s.skip_window === n.window;
  const fillNow = () => run(async () => {
    const r = await api.post<{ status: string; net_kobo: number; message: string; autofill: AutoFillState }>('/autofill/fill-now');
    onChange(r.autofill); await reload();
    if (r.status === 'success') koboSay('fill', `${N(r.net_kobo)} added. Your drips are covered until the next payday.`);
    else throw new Error(r.message || 'Your card was declined.');
  });
  const skip = (undo: boolean) => run(async () => { onChange(await api.post<AutoFillState>('/autofill/skip', undo ? { undo: true } : {})); toast(undo ? 'Payday fill is back on' : 'Skipped this payday'); });
  const off = () => openSheet(<>
    <h3>Turn off Auto-fill?</h3>
    <p className="muted" style={{ marginTop: -6 }}>We'll stop charging your card. Your drips keep running from your balance, so remember to top up.</p>
    <div style={{ display: 'flex', gap: 8 }}><button className="btn btn-soft" style={{ flex: 1 }} onClick={closeSheet}>Keep it on</button>
      <button className="btn btn-danger" style={{ flex: 1 }} onClick={async () => { closeSheet(); onChange(await api.post<AutoFillState>('/autofill/off')); toast('Auto-fill is off'); }}>Turn off</button></div>
  </>);
  return (<>
    <div className="card stack" style={{ gap: 10 }}>
      <div className="eyebrow">Next payday fill</div>
      {n ? (<>
        <div className="amt-display num" style={{ margin: 0, textAlign: 'left', fontSize: 32 }}>{n.amount_kobo ? N(n.amount_kobo) : 'Nothing needed'}</div>
        <span className="small muted">{skipped ? `Skipped: ${day(n.at)}` : `${day(n.at)}, ${time(n.at)}`}{n.covers_until && !skipped ? ` · covers your drips until ${day(n.covers_until)}` : ''}</span>
        {n.amount_kobo > 0 && <div className="kv small"><span className="muted">Card fee (Paystack)</span><b className="num">{N(n.fee_kobo)}</b></div>}
        {n.limited_by && <p className="small muted" style={{ margin: 0 }}>Capped by {n.limited_by === 'per_month' ? 'your monthly limit' : n.limited_by === 'per_charge' ? 'your limit per charge' : 'your balance limit'}, so some drips may still need a top-up.</p>}
        <p className="small muted" style={{ margin: 0 }}>The amount is an estimate. We work it out again that morning and message you before charging.</p>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button className="btn btn-primary" style={{ flex: 1 }} disabled={busy} onClick={fillNow}>I've been paid: fill now</button>
          {n.window && <button className="btn btn-soft" disabled={busy} onClick={() => skip(skipped)}>{skipped ? 'Undo skip' : 'Skip this payday'}</button>}
        </div>
      </>) : <span className="small muted">No payday window chosen. Auto-fill only tops up just before a drip that's short.</span>}
      {error && <p className="err" style={{ margin: 0 }}>{error}</p>}
    </div>
    <div className="list">
      <div className="set-row no-arrow"><span className="si">💳</span><span><b>{s.card ? cardLabel(s.card) : 'No card'}</b><span className="sub">{s.card?.exp ? `Expires ${s.card.exp}` : ''}</span></span><span /></div>
      <div className="set-row no-arrow"><span className="si">📅</span><span><b>When</b><span className="sub">{whenText(s)}</span></span><span /></div>
      <div className="set-row no-arrow"><span className="si">🧢</span><span><b>Limits</b><span className="sub">{N(s.max_per_charge_kobo ?? 0)} per charge · {N(s.max_per_month_kobo ?? 0)} a month · {N(s.used_this_month_kobo)} used this month</span></span><span /></div>
      <div className="set-row no-arrow"><span className="si">🧾</span><span><b>Card fees</b><span className="sub">{N(s.fees_last_30_days_kobo)} in the last 30 days</span></span><span /></div>
    </div>
    <div style={{ display: 'flex', gap: 8 }}>
      <button className="btn btn-soft" style={{ flex: 1 }} onClick={onEdit}>Change settings</button>
      <button className="btn btn-soft" style={{ flex: 1, color: 'var(--red)' }} onClick={off}>Turn off</button>
    </div>
  </>);
}

const whenText = (s: Pick<AutoFillState, 'payday_end' | 'payday_start' | 'just_in_time'>) => [
  s.payday_end && 'last 5 days of the month', s.payday_start && '1st to 5th', s.just_in_time && 'before a drip if short',
].filter(Boolean).join(' · ') || 'Nothing chosen';

function Setup({ s, cards, onSaved, onCancel }: { s: AutoFillState; cards: SavedCard[]; onSaved: (a: AutoFillState) => void; onCancel?: () => void }) {
  const { openSheet } = useStore();
  const [cardId, setCardId] = useState<number>(s.card?.id ?? cards[0].id);
  const [end, setEnd] = useState(s.payday_end);
  const [start, setStart] = useState(s.payday_start);
  const [jit, setJit] = useState(s.just_in_time);
  const [perCharge, setPerCharge] = useState(s.max_per_charge_kobo ?? s.suggested.max_per_charge_kobo);
  const [perMonth, setPerMonth] = useState(s.max_per_month_kobo ?? s.suggested.max_per_month_kobo);
  const card = cards.find((c) => c.id === cardId)!;
  const problem = !(end || start || jit) ? 'Choose at least one.' : perCharge < 100_000 ? 'The limit per charge must be at least ₦1,000.'
    : perMonth < perCharge ? "The monthly limit can't be lower than the limit per charge." : '';
  const consent = `I allow SpenDrip to charge ${cardLabel(card)} up to ${N(perCharge)} per charge and ${N(perMonth)} per month, ${[
    end && 'in the last 5 days of each month', start && 'on the 1st to the 5th of each month', jit && 'and up to a day before a drip my balance can’t cover',
  ].filter(Boolean).join(', ').replace(', and', ' and').replace(/^and /, '')}, to top up my SpenDrip balance, until I turn Auto-fill off.`;
  const body = { card_id: cardId, payday_end: end, payday_start: start, just_in_time: jit, max_per_charge_kobo: perCharge, max_per_month_kobo: perMonth };
  const money = (v: number, set: (n: number) => void, id: string, label: string) => (
    <div className="field"><label htmlFor={id}>{label}</label>
      <input id={id} inputMode="numeric" value={Math.round(v / 100) ? Math.round(v / 100).toLocaleString('en-NG') : ''} onChange={(e) => set(Number(e.target.value.replace(/\D/g, '')) * 100)} /></div>
  );
  return (
    <div className="card stack" style={{ gap: 14 }}>
      <div><b>Card</b>
        <div className="opt-list" style={{ marginTop: 8 }}>{cards.map((c) => (
          <button key={c.id} className="opt" aria-pressed={c.id === cardId} onClick={() => setCardId(c.id)}>
            <span>💳</span><span><b>{cardLabel(c)}</b><br /><span className="small muted">{[c.bank, c.exp && `Expires ${c.exp}`].filter(Boolean).join(' · ')}</span></span><span className="check">✓</span></button>
        ))}</div></div>
      <div><b>When</b>
        <div className="list" style={{ marginTop: 8 }}>
          <Row icon="🌙" title="End of month" sub="The last 5 days, when most salaries land" on={end} set={() => setEnd(!end)} />
          <Row icon="🌅" title="Start of month" sub="The 1st to the 5th" on={start} set={() => setStart(!start)} />
          <Row icon="⚡" title="Before a drip if I'm short" sub="Adds just what's missing, a day ahead. One try." on={jit} set={() => setJit(!jit)} />
        </div></div>
      <div><b>Limits</b>
        <p className="small muted" style={{ margin: '4px 0 8px' }}>Your drips need about {N(s.suggested.month_need_kobo)} a month right now, fees included.</p>
        {money(perCharge, setPerCharge, 'af-charge', 'Most per charge (₦)')}
        {money(perMonth, setPerMonth, 'af-month', 'Most per month (₦)')}</div>
      <div className="small" style={{ background: 'var(--soft, rgba(0,0,0,.04))', borderRadius: 12, padding: 12 }}>{consent}</div>
      {problem && <p className="err" style={{ margin: 0 }}>{problem}</p>}
      <div style={{ display: 'flex', gap: 8 }}>
        {onCancel && <button className="btn btn-soft" onClick={onCancel}>Cancel</button>}
        <button className="btn btn-primary" style={{ flex: 1 }} disabled={!!problem}
          onClick={() => openSheet(<ConfirmPin body={body} onSaved={onSaved} />)}>{s.active ? 'Save with PIN' : 'Agree and turn on'}</button>
      </div>
    </div>
  );
}

const Row = ({ icon, title, sub, on, set }: { icon: string; title: string; sub: string; on: boolean; set: () => void }) => (
  <button className="set-row no-arrow" onClick={set}><span className="si">{icon}</span><span style={{ minWidth: 0 }}><b>{title}</b><span className="sub">{sub}</span></span><Switch on={on} label={title} onChange={set} /></button>
);

function ConfirmPin({ body, onSaved }: { body: Record<string, unknown>; onSaved: (a: AutoFillState) => void }) {
  const { closeSheet, toast, koboSay } = useStore();
  const [pin, setPin] = useState('');
  const { error, setError, run } = useAction();
  const change = (v: string) => {
    setPin(v); setError('');
    if (v.length < 4) return;
    window.setTimeout(() => run(async () => {
      try {
        const a = await api.put<AutoFillState>('/autofill', { ...body, pin: v });
        closeSheet(); onSaved(a); toast('Auto-fill is on');
        koboSay('fill', a.next?.amount_kobo ? `Done. I'll top you up on ${day(a.next.at)}.` : "Done. I'll keep your drips topped up.");
      } catch (e) { setPin(''); throw e; }
    }), 180);
  };
  return (
    <>
      <h3 style={{ textAlign: 'center' }}>Enter your PIN to agree</h3>
      <PinDots n={pin.length} bad={!!error} />
      <p className="err">{error}</p>
      <PinPad value={pin} onChange={change} />
    </>
  );
}

function History({ s }: { s: AutoFillState }) {
  return (
    <div className="card stack" style={{ gap: 8 }}>
      <div className="eyebrow">Recent Auto-fills</div>
      {s.history.map((h, i) => (
        <div key={i} className="kv small">
          <span>{day(h.at)} · {h.kind === 'payday' ? 'Payday' : 'Before a drip'}{h.status === 'failed' ? <span className="muted"> · declined{h.reason && !h.reason.startsWith('limit') ? ` (${h.reason})` : ''}</span> : null}</span>
          <b className="num" style={h.status === 'failed' ? { color: 'var(--red)' } : undefined}>{h.amount_kobo ? N(h.amount_kobo) : '—'}</b>
        </div>
      ))}
    </div>
  );
}
