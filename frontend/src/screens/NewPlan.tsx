import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api } from '../lib/api';
import { addDaysISO, addMonthsISO, dateLabel, dayLabel, dayLabelY, fmtTime, ISO_WD, N, ord, todayISO } from '../lib/format';
import { useStore } from '../lib/store';
import { feeLines, feeTotal } from '../lib/fees';
import type { Draft, EndMode, Plan, Preview, Recipient, Tint } from '../lib/types';
import RankPicker from '../components/RankPicker';
import { Icon, Spinner, useAction } from '../components/ui';
import Kobo from '../components/Kobo';

const TINTS: Tint[] = ['cobalt', 'sun', 'hibiscus', 'mint'];
const EMOJIS = ['🍔', '🍲', '⛽', '💛', '🤝', '🏠', '📱', '🚕', '💡', '🎓', '💪', '🐷'];
const SUGGEST: [string, string][] = [['⛽', 'Fuel'], ['🍲', 'Upkeep'], ['📱', 'Data'], ['🏠', 'Rent'], ['💡', 'Light bill'], ['🐷', 'Savings']];

const fromPlan = (p: Plan): Draft => ({
  label: p.label, emoji: p.emoji, tint: p.tint, amount_kobo: p.amount_kobo, recipient_id: p.recipient.id, frequency: p.frequency,
  weekday: p.weekday ?? 5, month_day: p.month_day ?? 1, month_day_last: p.month_day_last, time_local: p.time_local, priority_rank: p.priority_rank ?? 0,
  start_date: p.start_date, end_mode: p.end_mode, duration_months: p.duration_months ?? 3,
  end_date: p.end_date ?? (p.last_drip_at ? p.last_drip_at.slice(0, 10) : addMonthsISO(todayISO(), 1)),
});

const MONTH_PICKS = [1, 3, 6, 12];
const monthsText = (n: number) => `${n} month${n === 1 ? '' : 's'}`;

export default function NewPlan() {
  const { id } = useParams();
  const editing = id ? Number(id) : null;
  const store = useStore();
  const { plans, recipients, reload, toast, confetti, openSheet, closeSheet, koboSay } = store;
  const nav = useNavigate();
  const existing = plans.find((p) => p.id === editing);
  const [params] = useSearchParams();
  const source = !editing ? plans.find((p) => p.id === Number(params.get('from'))) : undefined;
  const [d, setD] = useState<Draft>(() => existing ? (params.get('extend') && existing.state === 'finished'
    ? { ...fromPlan(existing), end_mode: 'date', end_date: addMonthsISO(todayISO(), 1) }  // extending: pick a new last day
    : fromPlan(existing)) : source ? {
    // "Run it again": same sentence, starting today, for the same length of time.
    ...fromPlan(source), start_date: todayISO(), end_mode: source.end_mode === 'ongoing' ? 'ongoing' : 'months',
    duration_months: source.duration_months ?? 3, priority_rank: 0,
  } : {
    label: 'Food', emoji: '🍔', tint: TINTS[plans.length % 4]!, amount_kobo: 1_000_000, recipient_id: recipients.find((r) => r.is_self)?.id ?? recipients[0]?.id ?? null,
    frequency: 'weekly', weekday: 5, month_day: 1, month_day_last: false, time_local: '14:00', priority_rank: 0,
    start_date: todayISO(), end_mode: 'ongoing', duration_months: 3, end_date: addMonthsISO(todayISO(), 1),
  });
  const startLocked = !!existing && existing.drips_done > 0;
  useEffect(() => { if (existing && params.get('extend')) window.setTimeout(() => openChip('end'), 300); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const [pulse, setPulse] = useState('');
  // Guide for new plans: the wave runs on every visit until the first tap; Kobo's bubble only on the first 3 visits (per device).
  const [explored, setExplored] = useState(!!editing);
  const [guided] = useState(() => { try { return Number(localStorage.getItem('sd-chip-guides') ?? 0); } catch { return 0; } });
  const markExplored = () => {
    if (explored) return;
    setExplored(true);
    try { localStorage.setItem('sd-chip-guides', String(guided + 1)); } catch { /* ignore */ }
  };
  const showKobo = !explored && guided < 3;
  // A brand-new plan can't be started until a word has been tapped at least once. Edits and "Run it again" are already yours.
  const touched = explored || !!editing || !!source;
  const [preview, setPreview] = useState<Preview | null>(null);
  const [previewErr, setPreviewErr] = useState('');
  const { busy, error, run } = useAction();
  const recipient = recipients.find((r) => r.id === d.recipient_id);
  useEffect(() => {
    if (d.recipient_id == null && recipients.length) setD((x) => ({ ...x, recipient_id: (recipients.find((r) => r.is_self) ?? recipients[0]!).id }));
  }, [recipients, d.recipient_id]);

  const body = useMemo(() => ({ ...d, weekday: d.frequency === 'weekly' ? d.weekday : null, month_day: d.frequency === 'monthly' && !d.month_day_last ? d.month_day : null,
    month_day_last: d.frequency === 'monthly' && d.month_day_last, plan_id: editing ?? undefined,
    start_date: !editing && d.start_date === todayISO() ? 'today' : d.start_date,
    duration_months: d.end_mode === 'months' ? d.duration_months : undefined, end_date: d.end_mode === 'date' ? d.end_date : undefined }), [d, editing]);

  useEffect(() => {
    if (!d.recipient_id) return;
    const t = window.setTimeout(() => {
      api.post<Preview>('/plans/preview', body).then((p) => { setPreview(p); setPreviewErr(''); }).catch((e) => setPreviewErr(e.message));
    }, 250);
    return () => window.clearTimeout(t);
  }, [body, d.recipient_id]);

  const set = (k: string, patch: Partial<Draft>) => { setD((x) => ({ ...x, ...patch })); setPulse(k); closeSheet(); };
  const chip = (k: string, label: React.ReactNode, on = false) => (
    <button className={`chip ${on ? 'on' : ''} ${pulse === k ? 'pulse' : ''}`} onClick={() => { markExplored(); openChip(k); }} key={k + String(label)}
      aria-haspopup="dialog">{label}<span className="chip-caret" aria-hidden="true">▾</span></button>
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
    if (k === 'start') openSheet(<StartSheet value={d.start_date} locked={startLocked} onDone={(v) => set('start', { start_date: v })} />);
    if (k === 'end') openSheet(<EndSheet draft={d} body={body} onDone={(patch) => set('end', patch)} />);
  };

  const save = () => run(async () => {
    const r = editing
      ? await api.patch<{ plan: Plan; dropped_priorities: string[] }>(`/plans/${editing}`, body)
      : await api.post<{ plan: Plan; dropped_priorities: string[] }>('/plans', body);
    await reload();
    nav('/plans');
    if (!editing) confetti();
    const first = r.plan.first_drip_at && r.plan.state === 'scheduled' ? `${dayLabelY(r.plan.first_drip_at)}, ${fmtTime(r.plan.time_local)}`
      : r.plan.next_at ? `${dayLabel(r.plan.next_at)}, ${fmtTime(r.plan.time_local)}` : 'soon';
    if (editing) toast(`${r.plan.label} updated`);
    else koboSay('celebrate', `${r.plan.label} is live! First drip ${first}.`);
    if (r.dropped_priorities.length) toast(`${r.dropped_priorities.join(', ')} is no longer a priority (max 3).`);
  });

  const when = d.frequency === 'daily' ? chip('freq', 'every day') : d.frequency === 'weekly'
    ? <>{chip('freq', 'every week')} on {chip('day', ISO_WD[d.weekday])}</>
    : <>{chip('freq', 'every month')} on {chip('day', d.month_day_last ? 'the last day' : 'the ' + ord(d.month_day))}</>;
  const startText = d.start_date === todayISO() ? 'starting today' : `starting ${dateLabel(d.start_date)}`;
  const endText = d.end_mode === 'ongoing' ? 'and keeps going' : d.end_mode === 'months' ? `for ${monthsText(d.duration_months)}` : `until ${dateLabel(d.end_date)}`;
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

  if (!recipients.length) {
    // Brand-new account: nobody to pay yet. Start with the person's own bank account.
    return (
      <div className="stack">
        <div className="close-row"><div className="eyebrow">New plan</div><button className="icon-btn" aria-label="Close" onClick={() => nav(-1)}>{Icon.close}</button></div>
        <div className="card stack" style={{ maxWidth: 520 }}>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}><Kobo mood="peek" size={56} />
            <div><b style={{ fontSize: 17 }}>First, where should your money land?</b><div className="small muted">Add your own bank account. You can add Mum, a cousin or anyone else next.</div></div></div>
          <AddRecipient self onSaved={(r) => setD((x) => ({ ...x, recipient_id: r.id }))} />
        </div>
      </div>
    );
  }
  return (
    <div className="stack">
      <div className="close-row"><div className="eyebrow">{editing ? 'Edit plan' : 'New plan'}</div><button className="icon-btn" aria-label="Close" onClick={() => nav(-1)}>{Icon.close}</button></div>
      <div className="cols cols-new"><div className="col stack">
        <p className={`sentence ${explored ? '' : 'tour'}`}>
          Send {chip('amount', N(d.amount_kobo))} for {chip('label', `${d.emoji} ${d.label}`)} to {chip('who', recipient?.label ?? 'someone')} {when} at {chip('time', fmtTime(d.time_local))},{' '}
          {chip('start', startText, d.start_date !== todayISO())} {chip('end', endText, d.end_mode !== 'ongoing')}.{' '}
          {chip('protect', shownRank ? `🛡 Priority ${shownRank}` : '＋ Protect it', !!shownRank)}
        </p>
        {!showKobo ? <p className="hint">👆 Tap any coloured word to change it.</p> : (
          <div className="chip-hint" role="note">
            <Kobo mood="point" size={56} title="Kobo pointing at the sentence" />
            <span className="bubble">Tap any coloured word to change it 👆<br /><span>Amount, who gets it, the day, when it starts and ends.</span></span>
          </div>
        )}
      </div><div className="col stack">
        <div className="card preview">
          <div className="eyebrow">Next drips</div>
          <div className="dates">{(preview?.next_dates ?? []).map((x) => <span key={x}>{dayLabel(x)}</span>)}</div>
          {preview?.total_drips != null && (
            <div className="whole">
              <div className="kv"><span className="muted">Whole plan</span><b className="num">{preview.total_drips} drip{preview.total_drips === 1 ? '' : 's'} · {N((preview.total_amount_kobo ?? 0) + (preview.total_fees_kobo ?? 0))}</b></div>
              <div className="kv sub"><span className="muted">{preview.first_drip_at ? `${dayLabelY(preview.first_drip_at)} → ` : ''}{preview.last_drip_at ? dayLabelY(preview.last_drip_at) : ''}</span><span className="muted num">incl. {N(preview.total_fees_kobo ?? 0)} fees</span></div>
            </div>
          )}
          {preview && <div className="kv"><span className="muted">Rest of this month</span><b className="num">{preview.runs_this_month} × {N(d.amount_kobo + preview.fee_kobo)} = {N(preview.month_cost_kobo)}</b></div>}
          <div className="fee-lines">
            <div className="kv"><span className="muted">Fees per drip</span><b className="num">{N(preview?.fee_kobo ?? feeTotal(d.amount_kobo, store.summary?.fees))}</b></div>
            {(preview?.fee_lines ?? feeLines(d.amount_kobo, store.summary?.fees)).map((l) => (
              <div key={l.kind} className="kv sub"><span className="muted">{l.label}</span><span className="num">{N(l.amount_kobo)}</span></div>
            ))}
          </div>
          {impact}
          {previewErr && <div className="impact warn">{previewErr}</div>}
          {recipient && !recipient.is_self && recipient.whatsapp && <div className="kv"><span className="muted">WhatsApp to {recipient.label}</span><b>On ✓</b></div>}
        </div>
        {error && <div className="error-card">{error}</div>}
        <div className="cta-bar">
          <button className="btn btn-primary btn-block" style={{ height: 56, fontSize: 16 }} disabled={busy || !!previewErr || !touched} onClick={save}>{editing ? 'Save changes' : 'Start this plan'}</button>
          {!touched && <p className="small muted" style={{ textAlign: 'center', margin: '8px 0 0' }}>Tap a coloured word above to make this plan yours.</p>}
        </div>
      </div></div>
    </div>
  );
}

function AmountSheet({ value, onDone }: { value: number; onDone: (kobo: number) => void }) {
  const { summary } = useStore();
  const [v, setV] = useState(String(Math.round(value / 100)));
  const lines = feeLines(+v * 100, summary?.fees);
  const total = lines.reduce((t, l) => t + l.amount_kobo, 0);
  const quick = [3000, 5000, 10000, 25000, 40000];
  const press = (k: string) => setV((x) => (k === '⌫' ? x.slice(0, -1) || '0' : ((x === '0' ? '' : x) + k).slice(0, 8)));
  return (
    <>
      <h3>How much each time?</h3>
      <div className="amt-display num">₦{Number(v || 0).toLocaleString('en-NG')}</div>
      <div className="quick">{quick.map((q) => <button key={q} aria-pressed={+v === q} onClick={() => setV(String(q))}>₦{q.toLocaleString('en-NG')}</button>)}</div>
      <div className="keypad">{['1', '2', '3', '4', '5', '6', '7', '8', '9', '000', '0', '⌫'].map((k) => <button key={k} aria-label={k === '⌫' ? 'Delete' : k} onClick={() => press(k)}>{k}</button>)}</div>
      <div className="small muted" style={{ marginBottom: 12 }}>
        Plus <b className="num">{N(total)}</b> per drip: {lines.map((l) => `${N(l.amount_kobo)} ${l.kind === 'service' ? 'SpenDrip fee' : l.label.replace(' (Paystack)', '').toLowerCase()}`).join(' · ')}. Minimum ₦100.
      </div>
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
  const [adding, setAdding] = useState<'' | 'self' | 'other'>('');
  if (adding) return <AddRecipient self={adding === 'self'} onSaved={(r) => onDone(r.id)} />;
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
        {!recipients.some((r) => r.is_self) && (
          <button className="opt" onClick={() => setAdding('self')}><span className="tile sm t-cobalt">🙋</span><span><b>My own account</b><br /><span className="small muted">Add the bank account money for you goes to</span></span><span /></button>
        )}
        <button className="opt" onClick={() => setAdding('other')}><span className="tile sm t-mint">＋</span><span><b>Someone new</b><br /><span className="small muted">Add their bank account</span></span><span /></button>
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
  const [testName, setTestName] = useState(false);
  const [checking, setChecking] = useState(false);
  const { busy, error, setError, run } = useAction();
  useEffect(() => { api.get<{ name: string; nip_code: string }[]>('/banks').then(setBanks); }, []);
  useEffect(() => {
    setName(''); setError(''); setTestName(false);
    if (acct.length === 10 && bank) {
      let live = true;
      const t = window.setTimeout(() => {
        setChecking(true);
        api.post<{ account_name: string; test_name?: boolean }>('/recipients/lookup', { nip_bank_code: bank, account_number: acct })
          .then((r) => { if (live) { setName(r.account_name); setTestName(!!r.test_name); } })
          .catch((e) => { if (live) setError(e.message); })
          .finally(() => { if (live) setChecking(false); });
      }, 300);
      return () => { live = false; window.clearTimeout(t); setChecking(false); };
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
        {checking && <Spinner label="Checking the account name…" />}
        {name && <div className="verified">✅ <span>{name}<br /><span className="small muted" style={{ fontWeight: 600 }}>Is this the right person?</span></span></div>}
        {name && testName && <p className="dev-note">Test mode: Paystack allows 3 real name checks a day and today's are used up, so this is a made-up test name.</p>}
        {error && <div className="error-card">{error}</div>}
        {!self && <div className="field"><label htmlFor="rw">WhatsApp number (optional)</label><input id="rw" inputMode="tel" placeholder="We'll message them when money lands" value={wa} onChange={(e) => setWa(e.target.value)} /></div>}
        <button className="btn btn-primary btn-block" disabled={!name || !label.trim() || busy} onClick={save}>Save</button>
      </div>
    </>
  );
}


/* ---------------- when it starts ---------------- */
function StartSheet({ value, locked, onDone }: { value: string; locked: boolean; onDone: (iso: string) => void }) {
  const today = todayISO();
  const [pick, setPick] = useState(value);
  const firstOfNext = addMonthsISO(today.slice(0, 8) + '01', 1);
  const opts: [string, string][] = [[today, 'Today'], [addDaysISO(today, 1), 'Tomorrow'], [firstOfNext, `1st of next month (${dateLabel(firstOfNext)})`]];
  if (locked) return (<>
    <h3>When it started</h3>
    <p className="muted">This plan started on {dateLabel(value)} and has already sent drips, so its start can't change. You can still change when it ends.</p>
  </>);
  return (<>
    <h3>When should it start?</h3>
    <div className="opt-list">{opts.map(([iso, label]) => (
      <button key={iso} className="opt" aria-pressed={value === iso} onClick={() => onDone(iso)}><span>📅</span><span><b>{label}</b></span><span className="check">✓</span></button>
    ))}</div>
    <div className="field" style={{ marginTop: 10 }}><label htmlFor="sd">Or pick a date</label>
      <input id="sd" type="date" min={today} max={addMonthsISO(today, 12)} value={pick} onChange={(e) => setPick(e.target.value)} /></div>
    <button className="btn btn-primary btn-block" disabled={!pick || pick < today} onClick={() => onDone(pick)}>Start {pick === today ? 'today' : `on ${pick ? dateLabel(pick) : '…'}`}</button>
    <p className="small muted">The first drip goes out on the first matching day from then.</p>
  </>);
}

/* ---------------- when it ends ---------------- */
function EndSheet({ draft, body, onDone }: { draft: Draft; body: Record<string, unknown>; onDone: (patch: Partial<Draft>) => void }) {
  const [mode, setMode] = useState<EndMode>(draft.end_mode);
  const [months, setMonths] = useState(draft.duration_months || 3);
  const minDate = draft.start_date > todayISO() ? draft.start_date : todayISO();
  const [date, setDate] = useState(draft.end_date < minDate ? addMonthsISO(minDate, 1) : draft.end_date);
  const [sum, setSum] = useState<Preview | null>(null);
  const [err, setErr] = useState('');
  useEffect(() => {
    if (mode === 'ongoing') { setSum(null); setErr(''); return; }
    const t = window.setTimeout(() => {
      api.post<Preview>('/plans/preview', { ...body, end_mode: mode, duration_months: mode === 'months' ? months : undefined, end_date: mode === 'date' ? date : undefined })
        .then((p) => { setSum(p); setErr(''); }).catch((e) => { setSum(null); setErr(e.message); });
    }, 200);
    return () => window.clearTimeout(t);
  }, [mode, months, date]); // eslint-disable-line react-hooks/exhaustive-deps
  const total = sum ? (sum.total_amount_kobo ?? 0) + (sum.total_fees_kobo ?? 0) : 0;
  return (<>
    <h3>When should it end?</h3>
    <div className="seg" role="group" aria-label="End">
      {([['ongoing', 'Keeps going'], ['months', 'For months'], ['date', 'Until a date']] as const).map(([k, l]) => (
        <button key={k} aria-pressed={mode === k} onClick={() => setMode(k)}>{l}</button>
      ))}
    </div>
    {mode === 'ongoing' && <p className="muted" style={{ margin: '12px 0' }}>It runs until you pause or delete it.</p>}
    {mode === 'months' && (
      <div className="stack" style={{ gap: 10, marginTop: 12 }}>
        <div className="quick">{MONTH_PICKS.map((n) => <button key={n} aria-pressed={months === n} onClick={() => setMonths(n)}>{monthsText(n)}</button>)}</div>
        <div className="stepper">
          <button aria-label="One month fewer" disabled={months <= 1} onClick={() => setMonths(months - 1)}>−</button>
          <b className="num">{monthsText(months)}</b>
          <button aria-label="One month more" disabled={months >= 36} onClick={() => setMonths(months + 1)}>＋</button>
        </div>
      </div>
    )}
    {mode === 'date' && (
      <div className="field" style={{ marginTop: 12 }}><label htmlFor="ed">Last day</label>
        <input id="ed" type="date" min={minDate} max={addMonthsISO(draft.start_date, 36)} value={date} onChange={(e) => setDate(e.target.value)} /></div>
    )}
    {mode !== 'ongoing' && (sum?.total_drips ? (
      <div className="end-sum">
        <span>Last drip <b>{sum.last_drip_at ? dayLabelY(sum.last_drip_at) : '—'}</b></span>
        <span><b className="num">{sum.total_drips}</b> drip{sum.total_drips === 1 ? '' : 's'} · <b className="num">{N(sum.total_amount_kobo ?? 0)}</b> plus <span className="num">{N(sum.total_fees_kobo ?? 0)}</span> fees</span>
        <span className="small muted">That's <b className="num">{N(total)}</b> in total. Paused drips aren't added on at the end.</span>
      </div>
    ) : err ? <div className="impact warn">{err}</div> : <Spinner label="Working it out…" />)}
    <button className="btn btn-primary btn-block" style={{ marginTop: 12 }} disabled={mode !== 'ongoing' && (!!err || !sum?.total_drips)}
      onClick={() => onDone(mode === 'months' ? { end_mode: mode, duration_months: months } : mode === 'date' ? { end_mode: mode, end_date: date } : { end_mode: 'ongoing' })}>
      Done
    </button>
  </>);
}
