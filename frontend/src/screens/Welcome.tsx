import { useState } from 'react';
import { Wordmark } from '../components/ui';
import Kobo, { type KoboMood } from '../components/Kobo';

type Slide = { h: string; p: string; v: React.ReactNode; kobo: KoboMood };

const TOP_UP: Slide = { kobo: 'fill', h: 'Top up once. Relax all month.', p: 'We add up what your month needs, fees included, and tell you the exact amount. Then we handle the rest.',
    v: <div className="vis vis-acct"><span className="small muted" style={{ fontWeight: 700 }}>Your SpenDrip account</span><span className="acct-no">8420 ••• •••</span>
      <span style={{ fontWeight: 700 }}>Wema Bank</span><div className="impact ok" style={{ marginTop: 6 }}>🎉 This month is covered</div></div> };

// The top-up slide opens and closes the tour: it's the clearest picture of how SpenDrip works.
const SLIDES: Slide[] = [
  TOP_UP,
  { kobo: 'idle', h: "Say it the way you'd say it.", p: '"Send ₦40,000 for fuel every Friday at 2 PM." That\'s a plan. Tap any word to change it.',
    v: <div className="vis vis-sentence">Send <span className="chip">₦40,000</span> for <span className="chip">⛽ Fuel</span> every <span className="chip">Friday</span> at <span className="chip">2:00 PM</span></div> },
  { kobo: 'happy', h: 'Protect what matters most.', p: 'Make Upkeep priority 1 and Mum priority 2. If money gets tight, they get paid in that order and other plans wait.',
    v: <div className="vis vis-bal"><div className="eyebrow">Your balance</div><div className="big-amt" style={{ fontSize: 30 }}>₦190,000</div>
      <div className="bar"><span className="seg-p" style={{ width: '80%' }} /><span className="seg-f" style={{ width: '20%' }} /></div>
      <div className="legend"><div><span className="k">🛡 Protected</span><b>₦151,550</b></div><div><span className="k">Free</span><b>₦38,450</b></div></div></div> },
  TOP_UP,
];

export default function Welcome({ onCreate, onSignIn }: { onCreate: () => void; onSignIn: () => void }) {
  const [i, setI] = useState(0);
  const s = SLIDES[i]!;
  const last = i === SLIDES.length - 1;
  return (
    <div className="onboard">
      <div className="ob-top"><Wordmark /><button className="link" onClick={() => setI(SLIDES.length - 1)}>{last ? '' : 'Skip'}</button></div>
      <div className="ob-body">
        <div className="ob-visual" key={i}><div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, width: '100%' }}><Kobo mood={s.kobo} size={64} follow />{s.v}</div></div>
        <div className="ob-copy">
          <div className="ob-slide"><h2>{s.h}</h2><p>{s.p}</p></div>
          {last ? (
            <div className="ob-ctrl" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <button className="btn btn-primary btn-block" style={{ height: 56 }} onClick={onCreate}>Create my account</button>
              <button className="btn btn-soft btn-block" onClick={onSignIn}>I already have an account</button>
            </div>
          ) : (
            <div className="ob-ctrl" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 14 }}>
              <div className="ob-dots">{SLIDES.map((_, k) => <i key={k} className={k === i ? 'on' : ''} />)}</div>
              <button className="btn btn-primary" style={{ minWidth: 140 }} onClick={() => setI(i + 1)}>Next</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
