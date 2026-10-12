import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { N } from '../lib/format';
import { useStore } from '../lib/store';
import Kobo from '../components/Kobo';
import { useAction } from '../components/ui';

export interface BoostState {
  enabled: boolean; month: string; prize_kobo: number; why_not: string | null; story_max: number;
  entry: { recipient_id: number | null; recipient: string; story: string; consent_publish: boolean } | null;
  winners: { month: string; first_name: string; for: string; story: string; prize_kobo: number }[];
}

const monthName = (m: string) => new Date(`${m}-01T12:00:00`).toLocaleDateString('en-NG', { month: 'long', year: 'numeric' });

/** SpenDrip Pays it forward: share who you look after; one story a month wins money for that person's drips. */
export default function Boost() {
  const nav = useNavigate();
  const { recipients, toast, koboSay } = useStore();
  const [s, setS] = useState<BoostState | null>(null);
  const [rid, setRid] = useState<number | null>(null);
  const [story, setStory] = useState('');
  const [consent, setConsent] = useState(false);
  const [editing, setEditing] = useState(false);
  const { busy, error, run } = useAction();
  useEffect(() => {
    api.get<BoostState>('/boost').then((b) => {
      setS(b); setRid(b.entry?.recipient_id ?? null); setStory(b.entry?.story ?? ''); setConsent(b.entry?.consent_publish ?? false);
    });
  }, []);
  if (!s) return <div className="stack"><div className="skeleton" /></div>;
  const people = recipients.filter((r) => !r.is_self && !r.label.endsWith('(removed)'));
  const save = () => run(async () => {
    const b = await api.post<BoostState>('/boost', { recipient_id: rid, story, consent_publish: consent });
    setS(b); setEditing(false); toast(s.entry ? 'Your story is updated' : "You're in!");
    if (!s.entry) koboSay('celebrate', `You're in for ${monthName(b.month)}. Good luck!`);
  });
  const showForm = s.enabled && !s.why_not && (!s.entry || editing);
  return (
    <div className="stack">
      <div className="close-row"><button className="link" onClick={() => nav(-1)}>← Back</button><span className="eyebrow">Pays it forward</span></div>
      <div><div className="eyebrow">Every month, one story wins</div>
        <h1 className="h1">{N(s.prize_kobo)} for someone you look after</h1></div>
      <div className="cols cols-profile"><div className="col stack">
        {!s.enabled ? (
          <div className="card small muted">Pays it forward isn't open yet. We'll let you know when it starts.</div>
        ) : s.why_not ? (
          <div className="card stack" style={{ gap: 8 }}><b>Almost there</b><span className="small muted">{s.why_not}</span>
            {s.why_not.startsWith('Verify') ? <button className="btn btn-primary" onClick={() => nav('/verify')}>Verify now</button>
              : s.why_not.startsWith('Set up a plan') ? <button className="btn btn-primary" onClick={() => nav('/plans/new')}>Set up a plan</button> : null}</div>
        ) : s.entry && !editing ? (
          <div className="card stack" style={{ gap: 10, alignItems: 'center', textAlign: 'center' }}>
            <Kobo mood="happy" size={80} />
            <b style={{ fontSize: 18 }}>You're in for {monthName(s.month)}</b>
            <span className="small muted">For {s.entry.recipient}: “{s.entry.story}”</span>
            <span className="small muted">We pick the winner in the first days of next month and tell them by email and in the app.</span>
            <button className="btn btn-soft" onClick={() => setEditing(true)}>Edit my story</button>
          </div>
        ) : null}
        {showForm && (
          <div className="card stack" style={{ gap: 12 }}>
            <div><b>Who do you look after?</b>
              {people.length ? (
                <div className="opt-list" style={{ marginTop: 8 }}>{people.map((r) => (
                  <button key={r.id} className="opt" aria-pressed={rid === r.id} onClick={() => setRid(r.id)}>
                    <span>{r.label[0]}</span><span><b>{r.label}</b></span><span className="check">✓</span></button>
                ))}</div>
              ) : <p className="small muted">Add the person first, from People.</p>}
            </div>
            <div className="field"><label htmlFor="boost-story">In a sentence or two, why do they matter to you?</label>
              <textarea id="boost-story" rows={4} maxLength={s.story_max} value={story} onChange={(e) => setStory(e.target.value)}
                placeholder="Mum raised four of us alone. Her upkeep is the first thing I send every month." style={{ width: '100%', font: 'inherit', padding: 12, borderRadius: 12, border: '1px solid var(--line)', background: 'transparent', color: 'inherit', resize: 'vertical' }} />
              <span className="small muted">{story.trim().length}/{s.story_max}</span></div>
            <label className="small" style={{ display: 'flex', gap: 8, alignItems: 'flex-start', cursor: 'pointer' }}>
              <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} style={{ marginTop: 3 }} />
              <span>If I win, SpenDrip may share my first name and my story. Never my surname or account details.</span>
            </label>
            {error && <p className="err" style={{ margin: 0 }}>{error}</p>}
            <div style={{ display: 'flex', gap: 8 }}>
              {editing && <button className="btn btn-soft" onClick={() => setEditing(false)}>Cancel</button>}
              <button className="btn btn-primary" style={{ flex: 1 }} disabled={busy || !rid || story.trim().length < 20} onClick={save}>{s.entry ? 'Save my story' : 'Enter for free'}</button>
            </div>
          </div>
        )}
      </div><div className="col stack">
        <div className="card act-sum">
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}><Kobo mood="celebrate" size={56} /><b>How it works</b></div>
          <p className="small muted" style={{ margin: 0 }}><b>Free to enter.</b> Any verified SpenDrip user with a plan can enter once a month. You don't need to top up.</p>
          <p className="small muted" style={{ margin: 0 }}><b>One winner a month.</b> We shortlist stories, then pick the winner with a random draw anyone can check.</p>
          <p className="small muted" style={{ margin: 0 }}><b>The prize lands by itself.</b> {N(s.prize_kobo)} is added to the winner's balance for the person they look after.</p>
          <p className="small muted" style={{ margin: 0 }}>🔒 We will never ask you to pay a fee or share your PIN to claim a prize. Anyone who does isn't SpenDrip.</p>
        </div>
        {s.winners.length > 0 && (
          <div className="card stack" style={{ gap: 8 }}><div className="eyebrow">Past winners</div>
            {s.winners.map((w) => <div key={w.month} className="small"><b>{w.first_name}</b>, for {w.for} · {monthName(w.month)}<br /><span className="muted">“{w.story}”</span></div>)}
          </div>
        )}
      </div></div>
    </div>
  );
}
