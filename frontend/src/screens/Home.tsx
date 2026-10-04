import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { countdown, dayLabel, fmtTime, greeting, lagos, MON, MONL, N, WD, toWhom } from '../lib/format';
import { useStore } from '../lib/store';
import { Icon, StatusPill, Wordmark } from '../components/ui';
import Kobo from '../components/Kobo';
import { openAppearance } from './Appearance';
import { VerifyCard } from './Verify';

export default function Home() {
  const [showAll, setShowAll] = useState(false);  // Coming up: 6 by default, the rest on request
  const store = useStore();
  const { summary, plans, me, reload, toast } = store;
  const nav = useNavigate();
  const [, tick] = useState(0);
  useEffect(() => { const t = window.setInterval(() => tick((n) => n + 1), 1000); return () => window.clearInterval(t); }, []);
  if (!summary) return <div className="stack"><div className="skeleton" /><div className="skeleton" /></div>;

  const f = summary.forecast;
  const bal = summary.balance.available_kobo;
  const byId = new Map(plans.map((p) => [p.id, p]));
  const month = MONL[lagos(new Date()).m - 1];
  const waits = f.events.filter((e) => e.status === 'wait');  // held back for money
  const capped = f.events.filter((e) => e.status === 'cap');  // held back by the daily sending limit
  const shorts = f.events.filter((e) => e.status === 'short');
  const prioNames = plans.filter((p) => p.priority_rank && p.status === 'active').sort((a, b) => a.priority_rank! - b.priority_rank!).map((p) => p.label);
  const prioText = prioNames.length ? prioNames.join(', ').replace(/, ([^,]*)$/, ' & $1') : 'your priorities';
  const protectedShown = Math.min(f.protected_kobo, bal);
  const pW = bal > 0 ? Math.min(100, (f.protected_kobo / bal) * 100) : 100;
  const next = f.events[0];
  const nextPlan = next && byId.get(next.plan_id);
  const initials = ((me?.user?.first_name?.[0] ?? '') + (me?.user?.last_name?.[0] ?? '')).toUpperCase();

  let headline = 'Your money is on schedule.';
  if (summary.paused_all) headline = 'Everything is paused.';
  else if (shorts.length) headline = 'Your priorities need a top-up.';
  else if (waits.length) headline = `${waits.length} drip${waits.length > 1 ? 's' : ''} waiting on a top-up.`;
  else if (!plans.length) headline = "Let's set up your first plan.";

  const resume = async () => { await api.patch('/me/settings', { paused_all: false }); await Promise.all([reload(), store.refreshMe()]); toast('All drips are back on'); };

  return (
    <div className="stack">
      {/* Phones: logo bar, then the greeting. Wide screens: greeting and buttons share one row, so both columns start level. */}
      <div className="home-head">
        <div className="topbar"><Wordmark />
          <span style={{ display: 'flex', gap: 8 }}>
            <button className="icon-btn" aria-label="Appearance" onClick={() => openAppearance(store)}>{Icon.look}</button>
            <button className="icon-btn" aria-label="Activity" onClick={() => nav('/activity')}>{Icon.bell}</button>
            <button className="avatar" aria-label="Profile" onClick={() => nav('/profile')}>{initials}</button>
          </span>
        </div>
        <div className="home-greet"><p className="hello">{greeting().text}{me?.user?.first_name ? `, ${me.user.first_name}` : ''} {greeting().emoji}</p><h1 className="h1">{headline}</h1></div>
      </div>
      <div className="cols cols-home"><div className="col stack">
        <div className="balance">
          <div className="eyebrow">Your balance</div>
          <div className="big-amt num">{N(bal)}</div>
          <div className="bar" role="img" aria-label={`Protected ${N(protectedShown)}, free ${N(Math.max(0, f.free_kobo))}`}>
            <span className="seg-p" style={{ width: `${pW}%` }} /><span className="seg-f" style={{ width: `${100 - pW}%` }} />
          </div>
          <div className="legend">
            <div><span className="k"><span className="sw" style={{ background: 'var(--hero-prot)' }} />Protected</span><b className="num">{N(protectedShown)}</b></div>
            <div><span className="k"><span className="sw" style={{ background: 'var(--hero-free)' }} />Free to spend</span><b className="num">{N(Math.max(0, f.free_kobo))}</b></div>
          </div>
          {summary.balance.held_kobo > 0 && <p className="small" style={{ margin: '8px 0 0', color: 'var(--hero-muted)' }}>{N(summary.balance.held_kobo)} is on its way to someone right now.</p>}
          <div className="bal-actions"><button className="btn btn-hero" onClick={() => nav('/fund')}>＋ Add money</button><button className="btn btn-ghost-w" onClick={() => nav('/plans/new')}>New plan</button></div>
        </div>
        <VerifyCard />
        {summary.paused_all ? (
          <div className="paused-banner"><span style={{ display: 'flex', alignItems: 'center', gap: 10 }}><Kobo mood="sleep" size={40} />All drips are paused</span><button className="btn btn-primary" style={{ height: 40 }} onClick={resume}>Resume</button></div>
        ) : shorts.length ? (
          <div className="forecast bad"><span className="kobo-corner"><Kobo mood="worried" size={52} /></span><h3>⚠️ Priorities short by {N(f.priority_shortfall_kobo)}</h3>
            <p>{prioText} can't all go out in {month}. Other plans are on hold until you top up.</p>
            <button className="btn btn-primary btn-block" onClick={() => nav('/fund')}>Top up {N(f.top_up_kobo)}</button></div>
        ) : waits.length ? (
          <div className="forecast warn"><span className="kobo-corner"><Kobo mood="waiting" size={52} /></span><h3>🛡 Priorities are safe for {month}</h3>
            <p>These drips will wait so {prioText} always get paid:</p>
            <div className="chips-row">
              {waits.slice(0, 4).map((e, i) => { const p = byId.get(e.plan_id); const d = lagos(e.at); return <span key={i} className="mini-chip">{p?.emoji} {p?.label} · {d.d} {MON[d.m - 1]}</span>; })}
              {waits.length > 4 && <span className="mini-chip">+{waits.length - 4} more</span>}
            </div>
            {f.top_up_kobo > 0
              ? <button className="btn btn-primary btn-block" onClick={() => nav('/fund')}>Top up {N(f.top_up_kobo)} to send everything</button>
              : <p className="small" style={{ margin: 0 }}>They'll go out once earlier drips have settled. Nothing to top up.</p>}
            {capped.length > 0 && <p className="small" style={{ margin: '8px 0 0' }}>{capped.length} more {capped.length === 1 ? 'is' : 'are'} over your daily sending limit. <button className="link small" onClick={() => nav('/profile')}>Raise it</button></p>}</div>
        ) : capped.length ? (
          <div className="forecast warn"><span className="kobo-corner"><Kobo mood="waiting" size={52} /></span><h3>🧢 Over your daily sending limit</h3>
            <p>The money is there, but these drips are bigger than what you've allowed SpenDrip to send in a day ({N(store.me?.user?.daily_cap_kobo ?? 0)} a day):</p>
            <div className="chips-row">
              {capped.slice(0, 4).map((e, i) => { const p = byId.get(e.plan_id); const d = lagos(e.at); return <span key={i} className="mini-chip">{p?.emoji} {p?.label} · {d.d} {MON[d.m - 1]}</span>; })}
              {capped.length > 4 && <span className="mini-chip">+{capped.length - 4} more</span>}
            </div>
            <button className="btn btn-primary btn-block" onClick={() => nav('/profile')}>Raise my daily limit</button></div>
        ) : plans.length ? (
          <div className="forecast ok"><span className="kobo-corner"><Kobo mood="happy" size={52} /></span><h3>🎉 All of {month} is covered</h3><p>Every drip this month will go out on time, fees included. Nothing to do.</p></div>
        ) : (
          <div className="forecast ok"><span className="kobo-corner"><Kobo mood="peek" size={52} follow /></span><h3>Start with one plan</h3><p>For example: ₦40,000 for fuel every Friday at 2 PM.</p>
            <button className="btn btn-primary btn-block" onClick={() => nav('/plans/new')}>Create a plan</button></div>
        )}
      </div><div className="col stack">
        {next && nextPlan && (
          <div className="card next"><div className={`tile t-${nextPlan.tint}`}>{nextPlan.emoji}</div>
            <div style={{ minWidth: 0 }}><div className="eyebrow">Next drip</div>
              <div style={{ fontWeight: 800, fontSize: 16 }}>{nextPlan.label} · {N(next.amount_kobo)} <span className="muted" style={{ fontWeight: 600 }}>to {toWhom(nextPlan)}</span></div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}><span className="cd num">{countdown(next.at)}</span><span className="small muted">{dayLabel(next.at)}, {fmtTime(next.at)}</span></div>
              <div style={{ marginTop: 4 }}><StatusPill status={next.status} /></div></div></div>
        )}
        <div className="section-h"><h2>Coming up</h2><button className="link" onClick={() => nav('/calendar')}>Calendar</button></div>
        <div className={`list coming ${showAll ? 'expanded' : ''}`}>
          {f.events.map((e, i) => {
            const p = byId.get(e.plan_id); if (!p) return null; const d = lagos(e.at);
            return (
              <button key={i} className={`row ${i >= 6 ? 'extra' : ''}`} onClick={() => nav(`/plans?open=${p.id}`)}>
                <span className="date"><span className="d1">{dayLabel(e.at) === 'Today' ? 'TODAY' : WD[d.wd]!.slice(0, 3).toUpperCase()}</span><span className="d2 num">{d.d}</span></span>
                <span className={`tile sm t-${p.tint}`}>{p.emoji}</span>
                <span style={{ minWidth: 0 }}><span className="t" style={{ display: 'block' }}>{p.label}</span><span className="s">{fmtTime(e.at)} · to {toWhom(p)}</span></span>
                <span style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}><span className="amt num">{N(e.amount_kobo)}</span><StatusPill status={e.status} /></span>
              </button>
            );
          })}
          {!f.events.length && <div className="row" style={{ gridTemplateColumns: '1fr' }}><span className="muted">Nothing else this month.</span></div>}
          {f.events.length > 6 && (
            <button className="row more" style={{ gridTemplateColumns: '1fr' }} onClick={() => setShowAll((v) => !v)} aria-expanded={showAll}>
              <span>{showAll ? 'Show fewer' : `View ${f.events.length - 6} more this month`}</span></button>
          )}
        </div>
      </div></div>
    </div>
  );
}
