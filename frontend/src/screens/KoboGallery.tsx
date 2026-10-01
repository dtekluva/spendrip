import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Kobo, { KOBO_MOODS } from '../components/Kobo';
import { useStore } from '../lib/store';

/** Every mood side by side. Tap one to see it pop up the way it does in the app. */
export default function KoboGallery() {
  const nav = useNavigate();
  const { koboSay } = useStore();
  const [key, setKey] = useState(0);
  return (
    <div className="stack">
      <div className="close-row"><button className="link" onClick={() => nav('/profile')}>← Profile</button><span className="eyebrow">Meet Kobo</span></div>
      <div className="stack" style={{ alignItems: 'center', textAlign: 'center', gap: 6 }}>
        <Kobo mood="idle" size={96} follow />
        <h1 className="h1" style={{ margin: 0 }}>Hi, I'm Kobo 👋</h1>
        <p className="muted" style={{ margin: 0, maxWidth: '40ch' }}>I'm the drop that carries your money where it needs to go, on time. Move your finger around and I'll watch it.</p>
      </div>
      <div className="kobo-gallery" key={key}>
        {KOBO_MOODS.map((m) => (
          <button key={m.mood} className="kobo-tile" onClick={() => koboSay(m.mood, m.when)}>
            <Kobo mood={m.mood} size={64} />
            <b>{m.label}</b>
            <span className="small muted">{m.when}</span>
          </button>
        ))}
      </div>
      <button className="btn btn-soft btn-block" onClick={() => setKey(key + 1)}>Replay all</button>
    </div>
  );
}
