import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Kobo, { KOBO_MOODS, koboEngine, type KoboMood } from '../components/Kobo';
import { useStore } from '../lib/store';

/** Compare the Rive and code versions, watch Rive blend between moods, and see every mood at once. */
export default function KoboGallery() {
  const nav = useNavigate();
  const { koboSay } = useStore();
  const [mood, setMood] = useState<KoboMood>('idle');
  const [tour, setTour] = useState(false);

  // "Play all": walk through every mood so the blends are easy to see.
  useEffect(() => {
    if (!tour) return;
    let i = KOBO_MOODS.findIndex((m) => m.mood === mood);
    const t = window.setInterval(() => {
      i = (i + 1) % KOBO_MOODS.length;
      setMood(KOBO_MOODS[i]!.mood);
      if (i === 0) setTour(false);
    }, 2200);
    return () => window.clearInterval(t);
  }, [tour]); // eslint-disable-line react-hooks/exhaustive-deps

  const current = KOBO_MOODS.find((m) => m.mood === mood)!;
  return (
    <div className="stack">
      <div className="close-row"><button className="link" onClick={() => nav('/profile')}>← Profile</button><span className="eyebrow">Meet Kobo</span></div>
      <div><h1 className="h1" style={{ margin: 0 }}>Hi, I'm Kobo 👋</h1>
        <p className="muted" style={{ margin: '4px 0 0', maxWidth: '46ch' }}>I'm the drop that carries your money where it needs to go, on time. Pick a mood and watch both versions of me switch.</p></div>

      <div className="card kobo-compare">
        <div className="kobo-side"><span className="eyebrow">Rive version</span><Kobo mood={mood} size={140} engine="rive" /><span className="small muted">Blends smoothly between moods</span></div>
        <div className="kobo-side"><span className="eyebrow">Code version</span><Kobo mood={mood} size={140} engine="svg" /><span className="small muted">Snaps to the new mood</span></div>
      </div>
      <div className="stack" style={{ gap: 10 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
          <b>{current.label} <span className="muted small" style={{ fontWeight: 600 }}>· {current.when}</span></b>
          <button className="link small" onClick={() => setTour(!tour)}>{tour ? 'Stop' : '▶ Play all moods'}</button>
        </div>
        <div className="quick">
          {KOBO_MOODS.map((m) => <button key={m.mood} aria-pressed={mood === m.mood} onClick={() => { setTour(false); setMood(m.mood); }}>{m.label}</button>)}
        </div>
      </div>

      <div className="section-h"><h2>All moods</h2><span className="small muted">Here: {koboEngine()} version · tap one to see its pop-up</span></div>
      <div className="kobo-gallery">
        {KOBO_MOODS.map((m) => (
          <button key={m.mood} className="kobo-tile" onClick={() => koboSay(m.mood, m.when)}>
            <Kobo mood={m.mood} size={64} />
            <b>{m.label}</b>
            <span className="small muted">{m.when}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
