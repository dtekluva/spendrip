import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../lib/api';
import { cadence, dateLabel, dayLabel, dayLabelY, fmtTime, N, toWhom } from '../lib/format';
import { useStore } from '../lib/store';
import type { Plan } from '../lib/types';
import RankPicker from '../components/RankPicker';
import { Icon, Switch } from '../components/ui';

/** "Drip 4 of 17 · ends Fri 29 Jan", "Starts Sun 1 Nov", "Ending soon" and the like. */
function planMeta(p: Plan) {
  const bounded = p.total_drips != null;
  const soon = p.state === 'active' && !!p.last_drip_at && new Date(p.last_drip_at).getTime() - Date.now() < 7 * 86_400_000;
  const pct = bounded && p.total_drips ? Math.min(100, Math.round((p.drips_done / p.total_drips) * 100)) : 0;
  return { bounded, soon, pct };
}

function Progress({ p }: { p: Plan }) {
  const { bounded, pct } = planMeta(p);
  if (!bounded || !p.total_drips) return null;
  return (
    <span className="plan-progress">
      <span className="small muted num">{p.drips_done ? `Drip ${Math.min(p.drips_done, p.total_drips!)} of ${p.total_drips}` : `${p.total_drips} drip${p.total_drips === 1 ? '' : 's'}`} · {p.state === 'finished' ? 'ended' : 'ends'} {p.last_drip_at ? dayLabelY(p.last_drip_at) : ''}</span>
      <span className="pbar" aria-hidden="true"><i style={{ width: `${pct}%` }} /></span>
    </span>
  );
}

export default function Plans() {
  const store = useStore();
  const { plans, summary, reload, toast, openSheet } = store;
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();

  useEffect(() => {
    const id = Number(params.get('open'));
    const p = plans.find((x) => x.id === id);
    if (p) { openSheet(<PlanSheet plan={p} />); setParams({}, { replace: true }); }
  }, [params, plans]); // eslint-disable-line react-hooks/exhaustive-deps

  const current = plans.filter((p) => p.state !== 'finished');
  const finished = plans.filter((p) => p.state === 'finished');
  const prio = plans.filter((p) => p.priority_rank).sort((a, b) => a.priority_rank! - b.priority_rank!);
  const total = summary?.forecast.total_needed_kobo ?? 0;
  const fees = (summary?.forecast.events ?? []).reduce((t, e) => t + (e.fee_kobo ?? 0), 0);

  const setRank = async (p: Plan, rank: number, undo?: () => void) => {
    const r = await api.patch<{ dropped_priorities: string[] }>(`/plans/${p.id}`, { priority_rank: rank });
    await reload();
    const msg = rank ? `${p.label} is priority ${Math.min(rank, prio.filter((x) => x.id !== p.id).length + 1)}` : `${p.label} is no longer a priority`;
    toast(r.dropped_priorities.length ? `${msg}. ${r.dropped_priorities.join(', ')} dropped out (max 3).` : msg, undo ? { label: 'Undo', run: undo } : undefined);
  };
  const togglePause = async (p: Plan) => {
    const status = p.status === 'active' ? 'paused' : 'active';
    await api.patch(`/plans/${p.id}`, { status }); await reload();
    toast(status === 'paused' ? `${p.label} paused` : `${p.label} is sending again`,
      status === 'paused' ? { label: 'Undo', run: async () => { await api.patch(`/plans/${p.id}`, { status: 'active' }); reload(); } } : undefined);
  };
  const addPriority = (slot: number) => {
    const cands = plans.filter((p) => !p.priority_rank);
    openSheet(<>
      <h3>Choose priority {slot}</h3>
      <div className="opt-list">
        {cands.map((p) => (
          <button key={p.id} className="opt" onClick={() => { store.closeSheet(); setRank(p, slot); }}>
            <span className={`tile sm t-${p.tint}`}>{p.emoji}</span><span><b>{p.label}</b><br /><span className="small muted">{N(p.amount_kobo)} · {cadence(p)}</span></span><span />
          </button>
        ))}
        {!cands.length && <p className="muted">Every plan is already a priority.</p>}
      </div>
    </>);
  };

  return (
    <div className="stack">
      <div className="topbar">
        <div><div className="eyebrow">{plans.filter((p) => p.status === 'active').length} active plans</div><h1 className="h1">Plans</h1></div>
        <button className="btn btn-soft" style={{ height: 44, padding: '0 14px' }} onClick={() => nav('/calendar')}>
          <span style={{ width: 18, height: 18, display: 'inline-grid' }}>{Icon.calendar}</span>Calendar</button>
      </div>
      <div className="cols cols-plans"><div className="col stack">
        <p className="muted col-head">Rest of this month: <b className="num" style={{ color: 'var(--ink)' }}>{N(total)}</b> including {N(fees)} in fees.</p>
        <div className="card prio-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}><span className="eyebrow">🛡 Priority order</span><span className="small muted">{prio.length}/3</span></div>
          {[0, 1, 2].map((i) => {
            const p = prio[i];
            if (!p) return <button key={i} className="prio-row empty" onClick={() => addPriority(i + 1)}><span className="rank">{i + 1}</span><span className="muted" style={{ fontWeight: 700 }}>＋ Add priority {i + 1}</span><span /></button>;
            return (
              <div key={p.id} className="prio-row"><span className="rank">{i + 1}</span>
                <span style={{ display: 'flex', gap: 10, alignItems: 'center', minWidth: 0 }}><span className={`tile sm t-${p.tint}`}>{p.emoji}</span>
                  <span style={{ minWidth: 0 }}><b>{p.label}</b><br /><span className="small muted">{N(p.amount_kobo)} · {cadence(p)}</span></span></span>
                <span style={{ display: 'flex', gap: 6 }}>
                  {i > 0 && <button className="mini-btn" aria-label={`Move ${p.label} up`} onClick={() => setRank(p, i)}>↑</button>}
                  <button className="mini-btn" aria-label={`Remove ${p.label} from priorities`} onClick={() => setRank(p, 0, () => setRank(p, i + 1))}>✕</button>
                </span>
              </div>
            );
          })}
          <p className="small muted" style={{ margin: '2px 0 0' }}>1 gets paid first. A lower priority never spends money a higher one still needs this month. Other plans only use what's left after all three.</p>
        </div>
      </div><div className="col stack">
        <div className="eyebrow col-head">All plans</div>
        <div className="plan-list">
          {current.map((p) => {
            const { soon } = planMeta(p);
            return (
              <button key={p.id} className={`plan-card ${p.status === 'paused' ? 'paused' : ''}`} onClick={() => openSheet(<PlanSheet plan={p} />)}>
                <span className={`tile t-${p.tint}`}>{p.emoji}</span>
                <span style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <span className="nm">{p.label} {p.priority_rank && <span className="pill p-prot">🛡 Priority {p.priority_rank}</span>}
                    {p.status === 'paused' && <span className="pill p-off">Paused</span>}
                    {p.state === 'scheduled' && <span className="pill p-sched">Starts {dateLabel(p.start_date)}</span>}
                    {soon && <span className="pill p-wait">Ending soon</span>}
                    {p.next_payout?.changed && <span className="pill p-wait">Next payout changed</span>}</span>
                  <span className="amt num">{N(p.amount_kobo)}</span>
                  <span className="small muted">{cadence(p)} · {fmtTime(p.time_local)} · to {toWhom(p)}</span>
                  <span className="small" style={{ fontWeight: 700 }}>{p.status === 'paused' ? 'Not sending'
                    : p.state === 'scheduled' && p.first_drip_at ? 'First drip: ' + dayLabelY(p.first_drip_at)
                    : p.next_at ? 'Next: ' + dayLabel(p.next_at) : ''}</span>
                  <Progress p={p} />
                </span>
                <Switch on={p.status === 'active'} label={`${p.status === 'active' ? 'Pause' : 'Resume'} ${p.label}`} onChange={() => togglePause(p)} />
              </button>
            );
          })}
          {!current.length && <div className="card">No plans running. Tap ＋ to make one.</div>}
        </div>
        {!!finished.length && (
          <details className="finished-list">
            <summary><span className="eyebrow">Finished · {finished.length}</span></summary>
            <div className="plan-list">
              {finished.map((p) => (
                <div key={p.id} className="plan-card done">
                  <span className={`tile t-${p.tint}`}>{p.emoji}</span>
                  <span style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <span className="nm">{p.label} <span className="pill p-off">Finished</span></span>
                    <span className="small muted">{N(p.amount_kobo)} · {cadence(p)} · to {toWhom(p)}</span>
                    <Progress p={p} />
                    <span className="done-actions">
                      <button className="btn btn-soft" onClick={() => nav(`/plans/${p.id}/edit?extend=1`)}>Extend</button>
                      <button className="btn btn-soft" onClick={() => nav(`/plans/new?from=${p.id}`)}>Run it again</button>
                    </span>
                  </span>
                </div>
              ))}
            </div>
          </details>
        )}
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-soft" style={{ flex: 1 }} onClick={() => nav('/plans/new')}>＋ New plan</button>
          <button className="btn btn-soft" style={{ flex: 1 }} onClick={() => nav('/plans/new?group=1')}>👥 Pay several people</button>
        </div>
      </div></div>
    </div>
  );
}

function PlanSheet({ plan }: { plan: Plan }) {
  const { plans, reload, toast, closeSheet, openSheet } = useStore();
  const nav = useNavigate();
  const [confirm, setConfirm] = useState(false);
  const p = plans.find((x) => x.id === plan.id) ?? plan;
  const rank = async (k: number) => {
    const r = await api.patch<{ dropped_priorities: string[] }>(`/plans/${p.id}`, { priority_rank: k });
    await reload();
    toast((k ? `${p.label} is a priority 🛡` : `${p.label} is no longer a priority`) + (r.dropped_priorities.length ? `. ${r.dropped_priorities.join(', ')} dropped out.` : ''));
    openSheet(<PlanSheet plan={p} />);
  };
  const pause = async () => {
    await api.patch(`/plans/${p.id}`, { status: p.status === 'active' ? 'paused' : 'active' }); await reload();
    openSheet(<PlanSheet plan={p} />);
  };
  const del = async () => {
    await api.del(`/plans/${p.id}`); await reload(); closeSheet(); toast(`${p.label} deleted. Past transfers stay in Activity.`);
  };
  return (
    <>
      <div style={{ display: 'flex', gap: 14, alignItems: 'center', marginBottom: 12 }}><span className={`tile t-${p.tint}`}>{p.emoji}</span>
        <div><h3 style={{ margin: 0 }}>{p.label}</h3><div className="muted small">{p.kind === 'group' || !p.recipient ? `${N(p.amount_kobo)} to ${toWhom(p)}, paid together`
          : `${N(p.amount_kobo)} to ${p.recipient.label} (${p.recipient.bank_name} ••${p.recipient.account_last4})`}</div></div></div>
      {p.kind === 'group' && <GroupPeople p={p} onEdit={() => { closeSheet(); nav(`/plans/${p.id}/edit?people=1`); }} />}
      <p style={{ margin: '0 0 6px', fontWeight: 600 }}>{cadence(p)} at {fmtTime(p.time_local)}.{p.state === 'scheduled' && p.first_drip_at ? ` Starts ${dayLabelY(p.first_drip_at)}.` : p.next_at ? ` Next: ${dayLabel(p.next_at)}.` : ''}</p>
      <p className="small muted" style={{ margin: '0 0 12px' }}>{p.end_mode === 'ongoing' ? 'Keeps going until you stop it.'
        : `${p.state === 'finished' ? 'Ran' : 'Runs'} ${p.end_mode === 'months' ? `for ${p.duration_months} month${p.duration_months === 1 ? '' : 's'}` : `until ${p.end_date ? dateLabel(p.end_date) : ''}`}`
        + (p.total_drips != null ? ` · ${p.total_drips} drips · ${N(p.total_cost_kobo ?? 0)} with fees` : '')}</p>
      {p.state === 'finished' ? (
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-primary" style={{ flex: 1 }} onClick={() => { closeSheet(); nav(`/plans/${p.id}/edit?extend=1`); }}>Extend</button>
          <button className="btn btn-soft" style={{ flex: 1 }} onClick={() => { closeSheet(); nav(`/plans/new?from=${p.id}`); }}>Run it again</button>
        </div>
      ) : (<>
      <div className="opt-list">
        <div className="opt" style={{ cursor: 'default', gridTemplateColumns: '1fr' }}>
          <span><b>🛡 Priority</b><br /><span className="small muted">1 is paid first. Lower priorities and other plans can't touch the money it needs.</span></span>
          <RankPicker plans={plans} id={p.id} current={p.priority_rank ?? 0} onPick={rank} />
        </div>
        <div className="opt" style={{ cursor: 'default' }}><span>⏯</span><span><b>Sending</b><br /><span className="small muted">Turn off to pause. Nothing is lost.</span></span>
          <Switch on={p.status === 'active'} label="Sending" onChange={pause} /></div>
      </div>
      </>)}
      <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
        <button className="btn btn-soft" style={{ flex: 1 }} onClick={() => { closeSheet(); nav(`/plans/${p.id}/edit`); }}>Edit plan</button>
        {!confirm && <button className="btn btn-soft" style={{ flex: 1, color: 'var(--red)' }} onClick={() => setConfirm(true)}>Delete</button>}
      </div>
      {confirm && (
        <div className="confirm" style={{ marginTop: 10 }}><b>Delete {p.label}?</b><span className="small muted">Future drips stop. Past transfers stay in Activity.</span>
          <div style={{ display: 'flex', gap: 8 }}><button className="btn btn-soft" style={{ flex: 1 }} onClick={() => setConfirm(false)}>Keep it</button>
            <button className="btn btn-danger" style={{ flex: 1 }} onClick={del}>Delete</button></div></div>
      )}
    </>
  );
}

/** A group plan's people, what each gets, and what the next payout will be after one-off changes. */
function GroupPeople({ p, onEdit }: { p: Plan; onEdit: () => void }) {
  const np = p.next_payout;
  return (
    <div className="g-sum" style={{ margin: '0 0 12px' }}>
      {(p.lines ?? []).map((l) => (
        <div key={l.recipient.id} className="kv sub"><span className="muted">{l.recipient.label} · {l.recipient.bank_name} ••{l.recipient.account_last4}
          {l.skip_next ? ' · skipped next time' : l.next_amount_kobo != null ? ` · ${N(l.next_amount_kobo)} next time` : ''}</span>
          <span className="num">{N(l.amount_kobo)}</span></div>
      ))}
      {np?.changed && <div className="kv"><span className="muted">Next payout</span><b className="num">{np.people} people · {N(np.amount_kobo + np.fee_kobo)} with fees</b></div>}
      <button className="btn btn-soft btn-block" style={{ marginTop: 6 }} onClick={onEdit}>Change people or amounts</button>
    </div>
  );
}
