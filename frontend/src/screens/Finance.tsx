import { useEffect, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { MON, MONL, N } from '../lib/format';
import { useStore } from '../lib/store';
import Kobo from '../components/Kobo';
import { useAction } from '../components/ui';

/*
 * Finance: the server sends a list of sections ({kind, id, title, priority, span, data}), each only when it applies.
 * One renderer per kind, all in the same card frame; kinds this app doesn't know are skipped, so new sections can ship
 * from the server first. Phones: one column in priority order. Wide screens: two columns, span-2 cards full width.
 */

interface Section { kind: string; id: string; title: string; priority: number; span: 1 | 2; data: any }
interface Cat { key: string; label: string; emoji: string; group: string }
interface Report { sections: Section[]; ai_status: 'fresh' | 'cached' | 'stale' | 'too_soon' | 'limit' | 'error' | 'none'; ai_updated_at: string | null; salary_kobo: number | null; categories: Cat[] }

const CAT_COLOURS: Record<string, string> = {
  housing: '#2F44F5', food: '#12B283', transport: '#FFB938', bills: '#7C5CFF', education: '#00A3C4', health: '#FF6B6B',
  staff: '#C27C00', family: '#FF4F8B', giving: '#B5651D', savings: '#0FA376', personal: '#8A93A6', other: '#B8BECC',
};
const monthLabel = (m: string) => MONL[Number(m.slice(5, 7)) - 1];
const shortMonth = (m: string) => MON[Number(m.slice(5, 7)) - 1];
const day = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString('en-NG', { day: 'numeric', month: 'short' });

function Change({ pct, good = 'down' }: { pct: number | null | undefined; good?: 'up' | 'down' }) {
  if (pct === null || pct === undefined) return null;
  const up = pct > 0;
  const tone = pct === 0 ? 'p-off' : (up === (good === 'up')) ? 'p-send' : 'p-wait';
  return <span className={`pill ${tone}`}>{pct === 0 ? 'Same' : `${up ? '▲' : '▼'} ${Math.abs(pct)}%`}</span>;
}

function Card({ s, right, children }: { s: Section; right?: ReactNode; children: ReactNode }) {
  return (
    <section className={`card fin-card ${s.span === 2 ? 'span-2' : ''}`} aria-labelledby={`fin-${s.id}`}>
      <header className="fin-h"><h2 id={`fin-${s.id}`}>{s.title}</h2>{right}</header>
      {children}
    </section>
  );
}

export default function Finance() {
  const nav = useNavigate();
  const [r, setR] = useState<Report | null>(null);
  const [aiBusy, setAiBusy] = useState(false);
  const askKobo = async (force = false) => {
    setAiBusy(true);
    try { setR(await api.post<Report>('/finance', force ? { force: true } : {})); } catch { /* keep the rules-based take */ } finally { setAiBusy(false); }
  };
  useEffect(() => {
    api.get<Report>('/finance').then((x) => { setR(x); if (x.ai_status !== 'cached') askKobo(); });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  if (!r) return <div className="stack"><div className="skeleton" /><div className="skeleton" /></div>;
  const ctx: Ctx = { r, setR, aiBusy, askKobo, nav };
  return (
    <div className="stack">
      <div><div className="eyebrow">Finance</div><h1 className="h1">Your money, in one picture</h1>
        <p className="small muted" style={{ margin: '4px 0 0' }}>Built from your drips and the costs you tell us about. General information, not financial advice.</p></div>
      <div className="fin-grid">
        {r.sections.map((s) => { const R = RENDERERS[s.kind]; return R ? <R key={s.id} s={s} ctx={ctx} /> : null; })}
      </div>
    </div>
  );
}

interface Ctx { r: Report; setR: (r: Report) => void; aiBusy: boolean; askKobo: (force?: boolean) => void; nav: ReturnType<typeof useNavigate> }
type Renderer = (p: { s: Section; ctx: Ctx }) => ReactNode;

/* ---------------------------------------------------------------- renderers */

const Insights: Renderer = ({ s, ctx }) => {
  const { openSheet } = useStore();
  const d = s.data;
  const icon: Record<string, string> = { plan: '➕', savings: '🐷', salary: '💼', family: '💛', general: '💡' };
  const act = (kind: string) => {
    if (kind === 'salary') openSheet(<SalarySheet ctx={ctx} />);
    else if (kind === 'savings') ctx.nav('/plans/new?label=Savings&emoji=🐷');
    else if (kind === 'plan') ctx.nav('/plans/new');
    else if (kind === 'family') ctx.nav('/people');
  };
  return (
    <Card s={s} right={<span className="small muted" style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
      {ctx.r.ai_updated_at && <span>Updated {new Date(ctx.r.ai_updated_at).toLocaleString('en-NG', { weekday: 'short', hour: 'numeric', minute: '2-digit', hour12: true })}</span>}
      <button className="link small" disabled={ctx.aiBusy} onClick={() => ctx.askKobo(true)}>{ctx.aiBusy ? 'Reading…' : 'Refresh'}</button></span>}>
      <div className="fin-take">
        <Kobo mood={ctx.aiBusy ? 'waiting' : 'happy'} size={64} />
        <p className={ctx.aiBusy && d.source !== 'ai' ? 'fin-shimmer' : ''}>{ctx.aiBusy && d.source !== 'ai' ? 'Kobo is reading your month…' : d.summary}</p>
      </div>
      {d.suggestions?.length > 0 && (
        <div className="fin-tips">{d.suggestions.map((t: any, i: number) => (
          <button key={i} className="fin-tip" onClick={() => act(t.kind)}>
            <span className="fin-tip-ic">{icon[t.kind] ?? '💡'}</span>
            <span><b>{t.title}</b><span className="small muted">{t.body}</span></span>
          </button>
        ))}</div>
      )}
      {ctx.r.ai_status === 'too_soon' && <p className="tiny muted" style={{ margin: 0 }}>Kobo read your month less than an hour ago. It updates by itself when your plans, pay or costs change.</p>}
      {ctx.r.ai_status === 'limit' && <p className="tiny muted" style={{ margin: 0 }}>Kobo has read your month enough for today. A fresh take tomorrow.</p>}
      {d.source === 'ai' && <p className="tiny muted" style={{ margin: 0 }}>Written by AI from your numbers. Check before acting.</p>}
    </Card>
  );
};

const Headline: Renderer = ({ s }) => {
  const d = s.data;
  return (
    <Card s={s} right={<span className="small muted">{monthLabel(d.month)}</span>}>
      <div className="fin-big num">{N(d.sent_kobo)}</div>
      <span className="small muted">sent in {d.drips} drip{d.drips === 1 ? '' : 's'} · {N(d.fees_kobo)} in fees · {N(d.topups_kobo)} added</span>
      <div className="kv" style={{ marginTop: 12 }}><span className="muted">{monthLabel(d.last_month)} in all</span>
        <span style={{ display: 'flex', gap: 6, alignItems: 'center' }}><b className="num">{N(d.last_sent_kobo)}</b><Change pct={d.last_change_pct} good="up" /></span></div>
      <div className="kv" style={{ marginTop: 6 }}><span className="muted">Balance now</span><b className="num">{N(d.balance_kobo)}</b></div>
    </Card>
  );
};

const Missing: Renderer = ({ s, ctx }) => {
  const { openSheet } = useStore();
  const d = s.data;
  const dismiss = async () => ctx.setR(await api.put<Report>('/finance/profile', { dismiss: s.id }));
  return (
    <Card s={s}>
      <div className="fin-take"><span className="fin-emoji">{d.emoji}</span>
        <p className="small" style={{ margin: 0 }}>Most homes pay for {d.examples}. Add it, even if you pay it another way, so your picture of the month is complete.</p></div>
      <div className="fin-actions">
        <button className="btn btn-primary" onClick={() => ctx.nav(`/plans/new?label=${encodeURIComponent(d.category === 'housing' ? 'Rent' : 'Feeding')}&emoji=${encodeURIComponent(d.emoji)}`)}>Add as a plan</button>
        <button className="btn btn-soft" onClick={() => openSheet(<ExpenseSheet ctx={ctx} category={d.category} label={d.category === 'housing' ? 'Rent' : 'Feeding'} />)}>I pay it elsewhere</button>
        <button className="link small" onClick={dismiss}>Not for me</button>
      </div>
    </Card>
  );
};

const Breakdown: Renderer = ({ s, ctx }) => {
  const { openSheet } = useStore();
  const d = s.data;
  const [open, setOpen] = useState(false);
  return (
    <Card s={s} right={<span className="small muted">A normal month · <b className="num">{N(d.total_kobo)}</b></span>}>
      <div className="fin-stack" role="img" aria-label={d.rows.map((x: any) => `${x.label} ${x.pct}%`).join(', ')}>
        {d.rows.map((x: any) => <span key={x.key} style={{ width: `${Math.max(x.pct, 1)}%`, background: CAT_COLOURS[x.key] }} />)}
      </div>
      <div className="fin-rows">
        {d.rows.map((x: any) => (
          <div key={x.key} className="fin-row"><span className="sw" style={{ background: CAT_COLOURS[x.key] }} />
            <span>{x.emoji} {x.label}</span><b className="num">{N(x.kobo)}</b><span className="small muted num" style={{ width: 38, textAlign: 'right' }}>{x.pct}%</span></div>
        ))}
      </div>
      <button className="link small" onClick={() => setOpen(!open)}>{open ? 'Hide' : 'See'} each plan and cost{open ? '' : ` (${d.plans.length + d.expenses.length})`}</button>
      {open && (
        <div className="fin-rows">
          {d.plans.map((p: any) => (
            <button key={p.plan_id} className="fin-row fin-row-btn" onClick={() => openSheet(<CategorySheet ctx={ctx} planId={p.plan_id} label={p.label} current={p.category} cats={d.categories} />)}>
              <span>{p.emoji}</span><span>{p.label}<br /><span className="tiny muted">{d.categories.find((c: Cat) => c.key === p.category)?.label}{p.category_source === 'user' ? '' : ' · tap to change'}</span></span>
              <b className="num">{N(p.total_kobo)}</b><span /></button>
          ))}
          {d.expenses.map((e: any) => (
            <div key={e.id} className="fin-row"><span>🧾</span><span>{e.label}<br /><span className="tiny muted">Paid elsewhere · {N(e.amount_kobo)} a {e.every}</span></span>
              <b className="num">{N(e.monthly_kobo)}</b>
              <button className="link small" style={{ color: 'var(--red)' }} onClick={async () => ctx.setR(await api.del<Report>(`/finance/expenses/${e.id}`))}>Remove</button></div>
          ))}
          <button className="btn btn-soft" onClick={() => openSheet(<ExpenseSheet ctx={ctx} />)}>＋ Add a cost you pay elsewhere</button>
        </div>
      )}
    </Card>
  );
};

const Salary: Renderer = ({ s, ctx }) => {
  const { openSheet } = useStore();
  const d = s.data;
  if (!d.salary_kobo) return (
    <Card s={s}>
      <p className="small muted" style={{ margin: 0 }}>Add your monthly take-home pay to see what share of it each part of your month takes. Only you see it.</p>
      <button className="btn btn-primary" onClick={() => openSheet(<SalarySheet ctx={ctx} />)}>Add take-home pay</button>
    </Card>
  );
  const guide: Record<string, string> = { needs: `guide: up to ${d.guide.needs}%`, family: `guide: family + wants up to ${d.guide.family_wants}%`, savings: `guide: ${d.guide.savings}% or more`, wants: '' };
  return (
    <Card s={s} right={<button className="link small" onClick={() => openSheet(<SalarySheet ctx={ctx} />)}>Edit</button>}>
      <div className="kv"><span className="muted">Take-home pay</span><b className="num">{N(d.salary_kobo)}</b></div>
      <div className="fin-meter"><span style={{ width: `${Math.min(100, d.planned_pct)}%` }} /></div>
      <span className="small muted">{d.planned_pct}% is planned · {d.left_kobo >= 0 ? `${N(d.left_kobo)} left over` : `${N(-d.left_kobo)} more than your pay`}</span>
      <div className="fin-rows" style={{ marginTop: 8 }}>
        {d.groups.map((g: any) => (
          <div key={g.key} className="fin-row"><span />
            <span>{g.label}<br /><span className="tiny muted">{guide[g.key]}</span></span><b className="num">{N(g.kobo)}</b><span className="small muted num" style={{ width: 38, textAlign: 'right' }}>{g.pct}%</span></div>
        ))}
      </div>
    </Card>
  );
};

const Trend: Renderer = ({ s }) => {
  const d = s.data;
  if (!d.months) return <Card s={s}><p className="small muted" style={{ margin: 0 }}>{d.note}</p></Card>;
  const max = Math.max(...d.months.map((m: any) => m.sent_kobo), 1);
  return (
    <Card s={s} right={<Change pct={d.last_change_pct} good="up" />}>
      <div className="fin-bars" role="img" aria-label={d.months.map((m: any) => `${monthLabel(m.month)} ${N(m.sent_kobo)}`).join(', ')}>
        {d.months.map((m: any) => (
          <div key={m.month} className="fin-bar">
            <span className="num tiny">{m.sent_kobo ? N(m.sent_kobo).replace(/,\d{3}$/, 'k') : ''}</span>
            <div className="fin-bar-col"><div style={{ height: `${(m.sent_kobo / max) * 100}%` }} /></div>
            <span className="tiny muted">{shortMonth(m.month)}</span>
          </div>
        ))}
      </div>
    </Card>
  );
};

const Family: Renderer = ({ s }) => {
  const d = s.data;
  return (
    <Card s={s}>
      <div className="fin-big num">{N(d.kobo)}<small>/mo</small></div>
      <span className="small muted">{d.pct_of_month}% of your month{d.pct_of_salary !== null ? ` · ${d.pct_of_salary}% of your pay` : ''}</span>
      {d.people.length > 0 && <p className="small" style={{ margin: '8px 0 0' }}>For {d.people.join(', ')} 💛</p>}
    </Card>
  );
};

const Next: Renderer = ({ s, ctx }) => {
  const d = s.data;
  return (
    <Card s={s} right={<span className="small muted">{monthLabel(d.month)}</span>}>
      <div className="kv"><span className="muted">A normal month needs</span><b className="num">{N(d.need_kobo)}</b></div>
      <div className="kv" style={{ marginTop: 6 }}><span className="muted">Your balance lasts until</span><b>about {day(d.lasts_until)}</b></div>
      {d.short_kobo > 0 && <button className="btn btn-primary" style={{ marginTop: 10 }} onClick={() => ctx.nav('/fund')}>Add {N(d.short_kobo)} for a full month</button>}
    </Card>
  );
};

const Savings: Renderer = ({ s, ctx }) => {
  const d = s.data;
  return (
    <Card s={s}>
      {!d.has_savings_plan && (
        <div className="fin-take"><span className="fin-emoji">🐷</span>
          <p className="small" style={{ margin: 0 }}><b>Pay yourself first.</b> A drip to your own savings account on payday makes saving automatic.</p>
          <button className="btn btn-soft" onClick={() => ctx.nav('/plans/new?label=Savings&emoji=🐷')}>Start a savings drip</button></div>
      )}
      <div className="fin-opts">{d.options.map((o: any) => (
        <div key={o.name} className="fin-opt">
          <span className="tiny muted">{o.kind}</span><b>{o.name}</b>
          <span className="small muted">{o.summary}</span>
          {o.rate_text ? <span className="small"><b>{o.rate_text}</b>{o.checked_on ? <span className="muted"> · checked {day(o.checked_on)}</span> : null}</span>
            : o.source_url ? <span className="small muted">Current rate: see the source</span> : null}
          {o.risk && <span className="tiny muted">Risk: {o.risk}</span>}
          {o.access && <span className="tiny muted">Access: {o.access}</span>}
          {o.source_url && <a className="small" href={o.source_url} target="_blank" rel="noopener">{o.source_name} ↗</a>}
        </div>
      ))}</div>
      <p className="tiny muted" style={{ margin: 0 }}>{d.disclaimer}</p>
    </Card>
  );
};

const RENDERERS: Record<string, Renderer> = {
  insights: Insights, headline: Headline, missing: Missing, breakdown: Breakdown, salary: Salary,
  trend: Trend, family: Family, next: Next, savings: Savings,
};

/* ---------------------------------------------------------------- sheets */

function SalarySheet({ ctx }: { ctx: Ctx }) {
  const { closeSheet, refreshMe } = useStore();
  const [v, setV] = useState(ctx.r.salary_kobo ?? 0);
  const { busy, error, run } = useAction();
  const save = (value: number | null) => run(async () => { ctx.setR(await api.put<Report>('/finance/profile', { salary_kobo: value })); refreshMe(); closeSheet(); ctx.askKobo(); });
  return (<>
    <h3>Your monthly take-home pay</h3>
    <p className="small muted" style={{ marginTop: -6 }}>What lands in your account each month after tax and deductions. Only you see it; it's used for your Finance report.</p>
    <div className="field"><label htmlFor="fin-sal">Take-home pay (₦)</label>
      <input id="fin-sal" inputMode="numeric" value={v ? Math.round(v / 100).toLocaleString('en-NG') : ''} onChange={(e) => setV(Number(e.target.value.replace(/\D/g, '')) * 100)} autoFocus /></div>
    {error && <p className="err">{error}</p>}
    <div style={{ display: 'flex', gap: 8 }}>
      {ctx.r.salary_kobo && <button className="btn btn-soft" disabled={busy} onClick={() => save(null)}>Remove</button>}
      <button className="btn btn-primary" style={{ flex: 1 }} disabled={busy || v < 1_000_000} onClick={() => save(v)}>Save</button>
    </div>
  </>);
}

function ExpenseSheet({ ctx, category = 'housing', label = '' }: { ctx: Ctx; category?: string; label?: string }) {
  const { closeSheet } = useStore();
  const [name, setName] = useState(label);
  const [cat, setCat] = useState(category);
  const [amount, setAmount] = useState(0);
  const [every, setEvery] = useState<'week' | 'month' | 'year'>(category === 'housing' ? 'year' : 'month');
  const { busy, error, run } = useAction();
  const save = () => run(async () => { ctx.setR(await api.post<Report>('/finance/expenses', { label: name, category: cat, amount_kobo: amount, every })); closeSheet(); ctx.askKobo(); });
  return (<>
    <h3>A cost you pay elsewhere</h3>
    <p className="small muted" style={{ marginTop: -6 }}>For money that doesn't go through SpenDrip, like rent paid straight to your landlord. It's only counted in your report.</p>
    <div className="field"><label htmlFor="ex-name">What is it?</label><input id="ex-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Rent" /></div>
    <div className="field"><label htmlFor="ex-amt">Amount (₦)</label>
      <input id="ex-amt" inputMode="numeric" value={amount ? Math.round(amount / 100).toLocaleString('en-NG') : ''} onChange={(e) => setAmount(Number(e.target.value.replace(/\D/g, '')) * 100)} /></div>
    <div className="quick">{(['week', 'month', 'year'] as const).map((x) => <button key={x} aria-pressed={every === x} onClick={() => setEvery(x)}>Every {x}</button>)}</div>
    <div className="field"><label htmlFor="ex-cat">Category</label>
      <select id="ex-cat" value={cat} onChange={(e) => setCat(e.target.value)}>{ctx.r.categories.map((c) => <option key={c.key} value={c.key}>{c.emoji} {c.label}</option>)}</select></div>
    {error && <p className="err">{error}</p>}
    <button className="btn btn-primary btn-block" disabled={busy || !name.trim() || amount < 10_000} onClick={save}>Add to my month</button>
  </>);
}

function CategorySheet({ ctx, planId, label, current, cats }: { ctx: Ctx; planId: string; label: string; current: string; cats: Cat[] }) {
  const { closeSheet } = useStore();
  const pick = async (key: string) => { ctx.setR(await api.put<Report>(`/finance/plans/${planId}/category`, { category: key })); closeSheet(); ctx.askKobo(); };
  return (<>
    <h3>What is {label} for?</h3>
    <div className="opt-list">{cats.map((c) => (
      <button key={c.key} className="opt" aria-pressed={c.key === current} onClick={() => pick(c.key)}><span>{c.emoji}</span><span><b>{c.label}</b></span><span className="check">✓</span></button>
    ))}</div>
  </>);
}
