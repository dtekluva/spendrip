import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../lib/api';
import { dayLabel, fmtTime, ISO_WD, N, ord } from '../lib/format';
import { useStore } from '../lib/store';
import type { Draft, Plan, Preview, Recipient, Tint } from '../lib/types';
import RankPicker from '../components/RankPicker';
import { Icon, useAction } from '../components/ui';

const TINTS: Tint[] = ['cobalt', 'sun', 'hibiscus', 'mint'];
const EMOJIS = ['🍔', '🍲', '⛽', '💛', '🤝', '🏠', '📱', '🚕', '💡', '🎓', '💪', '🐷'];
const SUGGEST: [string, string][] = [['⛽', 'Fuel'], ['🍲', 'Upkeep'], ['📱', 'Data'], ['🏠', 'Rent'], ['💡', 'Light bill'], ['🐷', 'Savings']];

const fromPlan = (p: Plan): Draft => ({
  label: p.label, emoji: p.emoji, tint: p.tint, amount_kobo: p.amount_kobo, recipient_id: p.recipient.id, frequency: p.frequency,
  weekday: p.weekday ?? 5, month_day: p.month_day ?? 1, month_day_last: p.month_day_last, time_local: p.time_local, priority_rank: p.priority_rank ?? 0,
});

export default function NewPlan() {
  const { id } = useParams();
  const editing = id ? Number(id) : null;
  const store = useStore();
  const { plans, recipients, reload, toast, confetti, openSheet, closeSheet } = store;
  const nav = useNavigate();
  const existing = plans.find((p) => p.id === editing);
  const [d, setD] = useState<Draft>(() => existing ? fromPlan(existing) : {
    label: 'Food', emoji: '🍔', tint: TINTS[plans.length % 4]!, amount_kobo: 1_000_000, recipient_id: recipients.find((r) => r.is_self)?.id ?? recipients[0]?.id ?? null,
    frequency: 'weekly', weekday: 5, month_day: 1, month_day_last: false, time_local: '14:00', priority_rank: 0,
  });
  const [pulse, setPulse] = useState('');
  const [preview, setPreview] = useState<Preview | null>(null);
  const [previewErr, setPreviewErr] = useState('');
  const { busy, error, run } = useAction();
  const recipient = recipients.find((r) => r.id === d.recipient_id);

  const body = useMemo(() => ({ ...d, weekday: d.frequency === 'weekly' ? d.weekday : null, month_day: d.frequency === 'monthly' && !d.month_day_last ? d.month_day : null,
    month_day_last: d.frequency === 'monthly' && d.month_day_last, plan_id: editing ?? undefined }), [d, editing]);

  useEffect(() => {
    if (!d.recipient_id) return;
    const t = window.setTimeout(() => {
      api.post<Preview>('/plans/preview', body).then((p) => { setPreview(p); setPreviewErr(''); }).catch((e) => setPreviewErr(e.message));
    }, 250);
    return () => window.clearTimeout(t);
  }, [body, d.recipient_id]);

  const set = (k: string, patch: Partial<Draft>) => { setD((x) => ({ ...x, ...patch })); setPulse(k); closeSheet(); };
  const chip = (k: string, label: React.ReactNode, on = false) => (
    <button className={`chip ${on ? 'on' : ''} ${pulse === k ? 'pulse' : ''}`} onClick={() => openChip(k)} key={k + String(label)}>{label}</button>
  );

  const openChip = (k: string) => {
    if (k === 'amount') openSheet(<AmountSheet value={d.amount_kobo} onDone={(v) => set('amount', { amount_kobo: v })} />);
    if (k === 'label') openSheet(<LabelSheet emoji={d.emoji} label={d.label} onDone={(emoji, label) => set('label', { emoji, label })} />);
    if (k === 'who') openSheet(<WhoSheet current={d.recipient_id} onDone={(rid) => set('who', { recipient_id: rid })} />);
    if (k === 'freq') openSheet(<>
      <h3>How often?</h3>
      <div className="opt-list">{([['daily', '☀️', 'Every day', 'Like upkeep or lunch money'], ['weekly', '📅', 'Every week', 'Pick a day, like Fuel on Fridays'], ['monthly', '🗓', 'Every month', 'Pick a date, like Mum on the 30th']] as const).map(([v, e, t, s]) => (
        <button key={v} className="opt" aria-pressed={d.frequency === v} onClick={() => set('freq', { frequency: v })}><span style={{ fontSize: 22 }}>{e}</span><span><b>{t}</b><br /><span className="small muted">{s}</span></span><span className="check">✓</span></button>
      ))}</div></>);
    if (k === 'day' && d.frequency === 'weekly') openSheet(<>
      <h3>Which day?</h3>
      <div className="grid7">{[1, 2, 3, 4, 5, 6, 7].map((i) => <button key={i} className="gbtn" aria-pressed={d.weekday === i} onClick={() => set('day', { weekday: i })}>{ISO_WD[i]!.slice(0, 2)}</button>)}</div></>);
    if (k === 'day' && d.frequency === 'monthly') openSheet(<>
      <h3>Which date?</h3>
      <div className="grid7">{Array.from({ length: 31 }, (_, i) => i + 1).map((i) => <button key={i} className="gbtn num" aria-pressed={!d.month_day_last && d.month_day === i} onClick={() => set('day', { month_day: i, month_day_last: false })}>{i}</button>)}</div>
      <button className="btn btn-soft btn-block" style={{ marginTop: 10 }} aria-pressed={d.month_day_last} onClick={() => set('day', { month_day_last: true })}>Last day of the month</button>
      <p className="small muted">Picked 29, 30 or 31? In shorter months it goes out on the last day.</p></>);
    if (k === 'time') openSheet(<TimeSheet value={d.time_local} onDone={(t) => set('time', { time_local: t })} />);
    if (k === 'protect') openSheet(<ProtectSheet draft={d} editing={editing} onDone={(r) => set('protect', { priority_rank: r })} />);
  };

  const save = () => run(async () => {
    const r = editing
      ? await api.patch<{ plan: Plan; dropped_priorities: string[] }>(`/plans/${editing}`, body)
      : await api.post<{ plan: Plan; dropped_priorities: string[] }>('/plans', body);
    await reload();
    nav('/plans');
    if (!editing) confetti();
    const first = r.plan.next_at ? `${dayLabel(r.plan.next_at)}, ${fmtTime(r.plan.time_local)}` : 'soon';
    toast(editing ? `${r.plan.label} updated` : `${r.plan.label} is live. First drip ${first}.` + (r.dropped_priorities.length ? ` ${r.dropped_priorities.join(', ')} is no longer a priority.` : ''));
  });

  const when = d.frequency === 'daily' ? chip('freq', 'every day') : d.frequency === 'weekly'
    ? <>{chip('freq', 'every week')} on {chip('day', ISO_WD[d.weekday])}</>
    : <>{chip('freq', 'every month')} on {chip('day', d.month_day_last ? 'the last day' : 'the ' + ord(d.month_day))}</>;
  const shownRank = d.priority_rank ? Math.min(d.priority_rank, plans.filter((p) => p.priority_rank && p.id !== editing).length + 1) : 0;

  let impact: React.ReactNode = null;
  if (preview) {
    const extra = preview.top_up_after_kobo - preview.top_up_before_kobo;
    if (!preview.runs_this_month) impact = <div className="impact ok">First drip is next month. Nothing extra needed this month.</div>;
    else if (d.priority_rank && preview.priorities_short_after_kobo > 0) impact = <div className="impact warn">Your priorities would be short. Top up {N(preview.priorities_short_after_kobo)} to keep them all safe.</div>;
    else if (preview.draft_waiting) impact = <div className="impact warn">{preview.draft_waiting} of {preview.runs_this_month} drip{preview.runs_this_month > 1 ? 's' : ''} would wait for a top-up. Add {N(Math.max(extra, 0))} to cover this month.</div>;
    else if (extra <= 0) impact = <div className="impact ok">✅ Fits in your free balance. Nothing to top up.</div>;
    else impact = <div className="impact warn">This plan fits, but other plans would need {N(extra)} more this month.</div>;
  }

  if (!recipients.length) return <div className="stack"><div className="skeleton" /></div>;
  return (
    <div className="stack">
      <div className="close-row"><div className="eyebrow">{editing ? 'Edit plan' : 'New plan'}</div><button className="icon-btn" aria-label="Close" onClick={() => nav(-1)}>{Icon.close}</button></div>
      <div className="cols cols-new"><div className="col stack">
        <p className="sentence">
          Send {chip('amount', N(d.amount_kobo))} for {chip('label', `${d.emoji} ${d.label}`)} to {chip('who', recipient?.label ?? 'someone')} {when} at {chip('time', fmtTime(d.time_local))}.{' '}
          {chip('protect', shownRank ? `🛡 Priority ${shownRank}` : '＋ Protect it', !!shownRank)}
        </p>
        <p className="hint">👆 Tap any coloured word to change it.</p>
      </div><div className="col stack">
        <div className="card preview">
          <div className="eyebrow">Next drips</div>
          <div className="dates">{(preview?.next_dates ?? []).map((x) => <span key={x}>{dayLabel(x)}</span>)}</div>
          {preview && <div className="kv"><span className="muted">Rest of this month</span><b className="num">{preview.runs_this_month} × {N(d.amount_kobo + preview.fee_kobo)} = {N(preview.month_cost_kobo)}</b></div>}
          <div className="kv"><span className="muted">Includes transfer fee</span><b className="num">{N(preview?.fee_kobo ?? 5000)} each</b></div>
          {impact}
          {previewErr && <div className="impact warn">{previewErr}</div>}
          {recipient && !recipient.is_self && recipient.whatsapp && <div className="kv"><span className="muted">WhatsApp to {recipient.label}</span><b>On ✓</b></div>}
        </div>
        {error && <div className="error-card">{error}</div>}
        <div className="cta-bar"><button className="btn btn-primary btn-block" style={{ height: 56, fontSize: 16 }} disabled={busy || !!previewErr} onClick={save}>{editing ? 'Save changes' : 'Start this plan'}</button></div>
      </div></div>
    </div>
  );
}

function AmountSheet({ value, onDone }: { value: number; onDone: (kobo: number) => void }) {
  const [v, setV] = useState(String(Math.round(value / 100)));
  const quick = [3000, 5000, 10000, 25000, 40000];
  const press = (k: string) => setV((x) => (k === '⌫' ? x.slice(0, -1) || '0' : ((x === '0' ? '' : x) + k).slice(0, 8)));
  return (
    <>
      <h3>How much each time?</h3>
      <div className="amt-display num">₦{Number(v || 0).toLocaleString('en-NG')}</div>
      <div className="quick">{quick.map((q) => <button key={q} aria-pressed={+v === q} onClick={() => setV(String(q))}>₦{q.toLocaleString('en-NG')}</button>)}</div>
      <div className="keypad">{['1', '2', '3', '4', '5', '6', '7', '8', '9', '000', '0', '⌫'].map((k) => <button key={k} aria-label={k === '⌫' ? 'Delete' : k} onClick={() => press(k)}>{k}</button>)}</div>
      <div className="small muted" style={{ marginBottom: 12 }}>Plus ₦50 transfer fee per drip. Minimum ₦100.</div>
      <button className="btn btn-primary btn-block" disabled={+v < 100} onClick={() => onDone(+v * 100)}>Done</button>
    </>
  );
}

function LabelSheet({ emoji, label, onDone }: { emoji: string; label: string; onDone: (e: string, l: string) => void }) {
  const [e, setE] = useState(emoji);
  const [l, setL] = useState(label);
  return (
    <>
      <h3>What's it for?</h3>
      <div className="emoji-grid">{EMOJIS.map((x) => <button key={x} aria-pressed={e === x} onClick={() => setE(x)}>{x}</button>)}</div>
      <div className="field"><label htmlFor="nm">Name</label><input id="nm" value={l} maxLength={40} autoComplete="off" onChange={(x) => setL(x.target.value)} /></div>
      <div className="quick" style={{ margin: '12px 0 16px' }}>{SUGGEST.map(([se, sl]) => <button key={sl} onClick={() => { setE(se); setL(sl); }}>{se} {sl}</button>)}</div>
      <button className="btn btn-primary btn-block" disabled={!l.trim()} onClick={() => onDone(e, l.trim())}>Done</button>
    </>
  );
}

function TimeSheet({ value, onDone }: { value: string; onDone: (t: string) => void }) {
  const [t, setT] = useState(value);
  const q = ['06:00', '09:00', '12:00', '14:00', '18:00', '21:00'];
  return (
    <>
      <h3>What time?</h3>
      <div className="quick" style={{ marginBottom: 14 }}>{q.map((x) => <button key={x} aria-pressed={value === x} onClick={() => onDone(x)}>{fmtTime(x)}</button>)}</div>
      <div className="field"><label htmlFor="tm">Or pick an exact time</label><input type="time" id="tm" value={t} onChange={(e) => setT(e.target.value)} /></div>
      <button className="btn btn-primary btn-block" style={{ marginTop: 14 }} onClick={() => t && onDone(t)}>Done</button>
    </>
  );
}

function ProtectSheet({ draft, editing, onDone }: { draft: Draft; editing: number | null; onDone: (rank: number) => void }) {
  const { plans } = useStore();
  const [r, setR] = useState(draft.priority_rank);
  const shown = r ? Math.min(r, plans.filter((p) => p.priority_rank && p.id !== editing).length + 1) : 0;
  return (
    <>
      <h3>Protect this plan?</h3>
      <p className="small muted" style={{ marginTop: -6 }}>Priorities get paid in order. Up to 3.</p>
      <RankPicker plans={plans} id={editing ?? 'draft'} current={shown} draftName={draft.label} onPick={setR} />
      <button className="btn btn-primary btn-block" style={{ marginTop: 16 }} onClick={() => onDone(r)}>Done</button>
    </>
  );
}

function WhoSheet({ current, onDone }: { current: number | null; onDone: (id: number) => void }) {
  const { recipients } = useStore();
  const [adding, setAdding] = useState(false);
  if (adding) return <AddRecipient onSaved={(r) => onDone(r.id)} />;
  return (
    <>
      <h3>Who gets it?</h3>
      <div className="opt-list">
        {recipients.filter((r) => !r.label.endsWith('(removed)')).map((r) => (
          <button key={r.id} className="opt" aria-pressed={current === r.id} onClick={() => onDone(r.id)}>
            <span className={`tile sm t-${r.is_self ? 'cobalt' : 'hibiscus'}`}>{r.is_self ? '🙋' : r.label[0]}</span>
            <span><b>{r.label}</b><br /><span className="small muted">{r.bank_name} ••{r.account_last4}{r.whatsapp ? ' · WhatsApp on' : ''}</span></span><span className="check">✓</span>
          </button>
        ))}
        <button className="opt" onClick={() => setAdding(true)}><span className="tile sm t-mint">＋</span><span><b>Someone new</b><br /><span className="small muted">Add their bank account</span></span><span /></button>
      </div>
    </>
  );
}

export function AddRecipient({ onSaved, self = false }: { onSaved: (r: Recipient) => void; self?: boolean }) {
  const { reload, toast } = useStore();
  const [banks, setBanks] = useState<{ name: string; nip_code: string }[]>([]);
  const [label, setLabel] = useState(self ? 'Me' : '');
  const [bank, setBank] = useState('');
  const [acct, setAcct] = useState('');
  const [wa, setWa] = useState('');
  const [name, setName] = useState('');
  const { busy, error, setError, run } = useAction();
  useEffect(() => { api.get<{ name: string; nip_code: string }[]>('/banks').then(setBanks); }, []);
  useEffect(() => {
    setName(''); setError('');
    if (acct.length === 10 && bank) {
      const t = window.setTimeout(() => api.post<{ account_name: string }>('/recipients/lookup', { nip_bank_code: bank, account_number: acct })
        .then((r) => setName(r.account_name)).catch((e) => setError(e.message)), 200);
      return () => window.clearTimeout(t);
    }
  }, [acct, bank]); // eslint-disable-line react-hooks/exhaustive-deps
  const save = () => run(async () => {
    const r = await api.post<Recipient>('/recipients', { label, nip_bank_code: bank, account_number: acct, whatsapp: wa, is_self: self });
    await reload(); toast(`Saved ${r.label} (${r.verified_account_name})`); onSaved(r);
  });
  return (
    <>
      <h3>{self ? 'Your own bank account' : 'Add someone'}</h3>
      <div className="stack" style={{ gap: 12 }}>
        {!self && <div className="field"><label htmlFor="rn">What do you call them?</label><input id="rn" placeholder="e.g. Sis Ada" value={label} onChange={(e) => setLabel(e.target.value)} /></div>}
        <div className="field"><label htmlFor="rb">Bank</label><select id="rb" value={bank} onChange={(e) => setBank(e.target.value)}><option value="">Choose bank</option>{banks.map((b) => <option key={b.nip_code} value={b.nip_code}>{b.name}</option>)}</select></div>
        <div className="field"><label htmlFor="ra">Account number</label><input id="ra" inputMode="numeric" maxLength={10} placeholder="10 digits" value={acct} onChange={(e) => setAcct(e.target.value.replace(/\D/g, ''))} /></div>
        {acct.length > 0 && acct.length < 10 && <span className="small muted">{10 - acct.length} more digit{10 - acct.length > 1 ? 's' : ''}…</span>}
        {name && <div className="verified">✅ <span>{name}<br /><span className="small muted" style={{ fontWeight: 600 }}>Is this the right person?</span></span></div>}
        {error && <div className="error-card">{error}</div>}
        {!self && <div className="field"><label htmlFor="rw">WhatsApp number (optional)</label><input id="rw" inputMode="tel" placeholder="We'll message them when money lands" value={wa} onChange={(e) => setWa(e.target.value)} /></div>}
        <button className="btn btn-primary btn-block" disabled={!name || !label.trim() || busy} onClick={save}>Save</button>
      </div>
    </>
  );
}
