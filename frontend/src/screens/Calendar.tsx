import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { dayLabel, fmtTime, kN, lagos, MONL, N, dayKey, toWhom } from '../lib/format';
import { useStore } from '../lib/store';
import type { DripEvent } from '../lib/types';
import { StatusPill } from '../components/ui';

const WAITING = new Set(['wait', 'short', 'cap', 'waited', 'failed', 'missed']);

export default function Calendar() {
  const { plans } = useStore();
  const nav = useNavigate();
  const today = lagos(new Date());
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<{ events: DripEvent[]; total_kobo: number } | null>(null);
  const [day, setDay] = useState<number | null>(null);
  const first = new Date(Date.UTC(today.y, today.m - 1 + offset, 1));
  const y = first.getUTCFullYear(), m = first.getUTCMonth() + 1;
  const dim = new Date(Date.UTC(y, m, 0)).getUTCDate();
  const lead = (new Date(Date.UTC(y, m - 1, 1)).getUTCDay() + 6) % 7;

  useEffect(() => {
    setData(null);
    api.get<{ events: DripEvent[]; total_kobo: number }>(`/calendar?month=${y}-${String(m).padStart(2, '0')}`).then((d) => {
      setData(d);
      const next = d.events.find((e) => new Date(e.at) >= new Date()) ?? d.events[0];
      setDay(next ? lagos(next.at).d : 1);
    });
  }, [y, m]);

  const byPlan = new Map(plans.map((p) => [p.id, p]));
  const byDay = new Map<number, DripEvent[]>();
  data?.events.forEach((e) => { const d = lagos(e.at).d; byDay.set(d, [...(byDay.get(d) ?? []), e]); });
  const sel = day ? byDay.get(day) ?? [] : [];
  const waiting = data?.events.filter((e) => WAITING.has(e.status)).length ?? 0;

  return (
    <div className="stack">
      <div className="close-row"><button className="link" onClick={() => nav('/plans')}>← Plans</button><span className="eyebrow">Calendar</span></div>
      <div className="cols cols-cal"><div className="col stack">
        <div className="cal-head">
          <button className="icon-btn" aria-label="Previous month" disabled={offset <= -3} style={{ opacity: offset <= -3 ? 0.35 : 1 }} onClick={() => setOffset(offset - 1)}>‹</button>
          <div style={{ textAlign: 'center' }}><h1 className="h1" style={{ margin: 0 }}>{MONL[m - 1]} {y}</h1>
            <span className="small muted num">{data ? `${data.events.length} drips · ${N(data.total_kobo)} with fees` : 'Loading…'}{waiting ? <> · <b style={{ color: 'var(--amber)' }}>{waiting} waiting</b></> : null}</span></div>
          <button className="icon-btn" aria-label="Next month" disabled={offset >= 2} style={{ opacity: offset >= 2 ? 0.35 : 1 }} onClick={() => setOffset(offset + 1)}>›</button>
        </div>
        <div className="cal-grid">
          {['M', 'T', 'W', 'T', 'F', 'S', 'S'].map((d, i) => <span key={i} className="cal-wd">{d}</span>)}
          {Array.from({ length: lead }, (_, i) => <span key={`l${i}`} />)}
          {Array.from({ length: dim }, (_, i) => i + 1).map((d) => {
            const list = byDay.get(d) ?? [];
            const tints = [...new Set(list.map((e) => byPlan.get(e.plan_id)?.tint ?? 'cobalt'))].slice(0, 4);
            const isToday = offset === 0 && d === today.d;
            const past = offset < 0 || (offset === 0 && d < today.d);
            const cls = ['cal-day', isToday ? 'today' : '', past ? 'past' : '', list.some((e) => WAITING.has(e.status)) ? 'wait' : ''].join(' ');
            return (
              <button key={d} className={cls} aria-pressed={day === d} aria-label={`${d} ${MONL[m - 1]}, ${list.length} drips`} onClick={() => setDay(d)}>
                <span className="num">{d}</span>
                <span className="cal-dots">{tints.map((t) => <i key={t} className={`d-${t}`} />)}</span>
                <span className="cal-amt num">{list.length ? kN(list.reduce((s, e) => s + e.amount_kobo, 0)) : ''}</span>
              </button>
            );
          })}
        </div>
        <div className="cal-legend">{plans.filter((p) => p.status === 'active').map((p) => <span key={p.id}><i className={`d-${p.tint}`} />{p.label}</span>)}<span><i className="wait-mark" />Waits for top-up</span></div>
      </div><div className="col stack">
        <div className="section-h"><h2>{day ? dayLabel(new Date(Date.UTC(y, m - 1, day, 12))) : ''}</h2><span className="small muted num">{sel.length ? N(sel.reduce((s, e) => s + e.amount_kobo, 0)) : ''}</span></div>
        <div className="list">
          {sel.map((e, i) => {
            const p = byPlan.get(e.plan_id);
            return (
              <button key={i} className="row" style={{ gridTemplateColumns: 'auto 1fr auto' }} onClick={() => p && nav(`/plans?open=${p.id}`)}>
                <span className={`tile sm t-${p?.tint ?? 'cobalt'}`}>{p?.emoji ?? '💸'}</span>
                <span style={{ minWidth: 0 }}><span className="t" style={{ display: 'block' }}>{p?.label ?? 'Deleted plan'} {e.rank ? <span className="pill p-prot">🛡 {e.rank}</span> : null}
                  {p?.first_drip_at && dayKey(p.first_drip_at) === dayKey(e.at) && p.total_drips != null ? <span className="pill p-sched">First drip</span> : null}
                  {p?.last_drip_at && dayKey(p.last_drip_at) === dayKey(e.at) ? <span className="pill p-wait">🏁 Last drip</span> : null}</span>
                  <span className="s">{fmtTime(e.at)}{p ? ` · to ${toWhom(p)}` : ''}</span></span>
                <span style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}><span className="amt num">{N(e.amount_kobo)}</span><StatusPill status={e.status} /></span>
              </button>
            );
          })}
          {!sel.length && <div className="row" style={{ gridTemplateColumns: '1fr' }}><span className="muted">No drips this day.</span></div>}
        </div>
        {offset > 0 && <p className="small muted" style={{ margin: 0 }}>Future months show what's scheduled. Protection is worked out when the month starts.</p>}
      </div></div>
    </div>
  );
}
