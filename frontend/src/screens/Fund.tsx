import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Kobo from '../components/Kobo';
import type { AutoFillState } from './AutoFill';
import { api } from '../lib/api';
import { lagos, MONL, N } from '../lib/format';
import { useStore } from '../lib/store';
import { useAction } from '../components/ui';
import { CardPanel } from './CardTopUp';
import { feeTotal } from '../lib/fees';
import { VerifyCard } from './Verify';

export default function Fund() {
  const { summary, plans, me, reload, confetti, koboSay, toast } = useStore();
  const { busy, run } = useAction();
  const nav = useNavigate();
  if (!summary) return <div className="stack"><div className="skeleton" /></div>;
  const f = summary.forecast;
  const feeOf = (amount: number) => feeTotal(amount, summary.fees);
  const month = MONL[lagos(new Date()).m - 1];
  const fa = summary.funding_account;
  const verified = me?.user?.kyc_status === 'verified';
  const counts = new Map<number, number>();
  f.events.forEach((e) => counts.set(e.plan_id, (counts.get(e.plan_id) ?? 0) + 1));
  const prio = plans.filter((p) => p.priority_rank).sort((a, b) => a.priority_rank! - b.priority_rank!);
  const groups: [string, typeof plans][] = [...prio.map((p) => [`🛡 Priority ${p.priority_rank}`, [p]] as [string, typeof plans]), ['Other plans', plans.filter((p) => !p.priority_rank)]];
  const number = fa?.account_number.replace(/(\d{4})(\d{3})(\d{3})/, '$1 $2 $3') ?? '';

  const copy = async () => {
    try { await navigator.clipboard.writeText(fa!.account_number); toast('Account number copied'); }
    catch { toast(`Your account number: ${number}`); }
  };
  const simulate = (amount: number) => run(async () => {
    await api.post('/dev/top-up', { amount_naira: amount / 100 });
    await reload();
    const covered = amount >= f.top_up_kobo;
    if (covered) confetti();
    koboSay(covered ? 'celebrate' : 'fill', covered ? `Yum, ${N(amount)}! ${month} is fully covered.` : `${N(amount)} in. ${N(f.top_up_kobo - amount)} more covers everything.`);
  });

  return (
    <div className="stack">
      <div><div className="eyebrow">Add money</div><h1 className="h1">{f.top_up_kobo ? `Top up ${N(f.top_up_kobo)} to cover ${month}` : `${month} is covered 🎉`}</h1></div>
      <div className="cols cols-fund"><div className="col stack">
        {fa ? (
          <div className="acct">
            <span className="small muted" style={{ fontWeight: 700 }}>Send a bank transfer to your SpenDrip account</span>
            <span className="acct-no num">{number}</span>
            <span style={{ fontWeight: 700 }}>{fa.bank_name} · {fa.account_name}</span>
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <button className="btn btn-primary" style={{ flex: 1 }} onClick={copy}>Copy number</button>
              <button className="btn btn-soft" onClick={() => document.getElementById('card-panel')?.scrollIntoView({ behavior: 'smooth' })}>Pay with card or bank</button>
            </div>
            <span className="small muted">Transfers usually land in under a minute. We'll notify you.</span>
          </div>
        ) : verified ? <div className="card small muted">Top up below by card, from your bank account, or by bank transfer, all through Paystack.</div> : <VerifyCard />}
        {verified && me?.user?.limits && <p className="small muted" style={{ margin: 0 }}>Your account can hold up to {N(me.user.limits.max_balance_kobo)} for now.</p>}
        {verified && <AutoFillCard onOpen={() => nav('/autofill')} />}
        {verified && <div id="card-panel"><CardPanel suggested={f.top_up_kobo} /></div>}
        {me?.dev_tools && verified && (
          <div className="demo">
            <div className="eyebrow">Test mode</div>
            <span className="small muted">No real money moves yet. Pretend a transfer just arrived in your SpenDrip account.</span>
            <div className="quick">{[...new Set([f.top_up_kobo, 2_000_000, 5_000_000].filter((x) => x > 0))].map((x) => <button key={x} disabled={busy} onClick={() => simulate(x)}>{N(x)}</button>)}</div>
          </div>
        )}
      </div><div className="col stack">
        <div className="section-h"><h2>What {month} still needs</h2></div>
        <div className="table">
          {groups.map(([g, ps]) => {
            const rows = ps.filter((p) => counts.get(p.id));
            if (!rows.length) return null;
            return (
              <div key={g}>
                <div className="tgroup">{g}</div>
                {rows.map((p) => { const n = counts.get(p.id)!; return (
                  <div key={p.id} className="trow"><span className={`tile sm t-${p.tint}`}>{p.emoji}</span>
                    <span><b>{p.label}</b><br /><span className="small muted num">{n} × ({N(p.amount_kobo)} + {N(feeOf(p.amount_kobo))} fees)</span></span><b className="num">{N(n * (p.amount_kobo + feeOf(p.amount_kobo)))}</b></div>
                ); })}
              </div>
            );
          })}
          {!f.events.length && <div className="trow"><span /><span className="muted">No drips left this month.</span><span /></div>}
          <div className="ttotal" style={{ borderTop: '1px solid var(--line)', marginTop: 6, paddingTop: 12 }}><span>Priorities need</span><b className="num">{N(f.protected_kobo)}</b></div>
          <div className="ttotal"><span>Everything needs</span><b className="num">{N(f.total_needed_kobo)}</b></div>
          <div className="ttotal"><span>You have</span><b className="num">− {N(summary.balance.available_kobo)}</b></div>
          <div className="ttotal final"><span>Top up</span><span className="num">{N(f.top_up_kobo)}</span></div>
        </div>
      </div></div>
    </div>
  );
}

/** Auto-fill, front and centre on Add money: what it is when it's off, what's next when it's on. */
function AutoFillCard({ onOpen }: { onOpen: () => void }) {
  const [a, setA] = useState<AutoFillState | null>(null);
  useEffect(() => { api.get<AutoFillState>('/autofill').then(setA).catch(() => {}); }, []);
  if (a && !a.enabled) return null;
  const on = a?.active;
  const next = on && a?.next ? `Next: ${new Date(a.next.at).toLocaleDateString('en-NG', { weekday: 'short', day: 'numeric', month: 'short' })}${a.next.amount_kobo ? `, about ${N(a.next.amount_kobo)}` : ''}` : '';
  return (
    <div className="autofill-card">
      <Kobo mood="fill" size={56} />
      <div style={{ minWidth: 0, flex: 1 }}>
        <span className="pill" style={{ background: on ? 'var(--mint)' : 'var(--sun)', color: '#0B1040' }}>{on ? '⛽ Auto-fill is on' : a?.paused_reason ? 'Auto-fill paused' : 'New'}</span>
        <b style={{ display: 'block', margin: '6px 0 2px', fontSize: 17 }}>{on ? 'Your drips top themselves up' : 'Never top up by hand again'}</b>
        <span className="small muted">{on ? next || 'Before a drip, if you\u2019re short.' : 'Auto-fill tops up from your card on payday, and before a drip if you\u2019re short. You set the limits.'}</span>
      </div>
      <button className={`btn ${on ? 'btn-soft' : 'btn-primary'}`} onClick={onOpen}>{on ? 'Manage' : 'Set up'}</button>
    </div>
  );
}
