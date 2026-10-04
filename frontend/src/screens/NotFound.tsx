import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import Kobo from '../components/Kobo';

/** Any address inside the app that doesn't exist. Two moods, picked at random each time: puzzled Kobo or chilling Kobo. */
export default function NotFound() {
  const nav = useNavigate();
  const { pathname } = useLocation();
  const [chill] = useState(() => Math.random() < 0.5);
  return (
    <div className="stack" style={{ alignItems: 'center', textAlign: 'center', maxWidth: 460, margin: '0 auto', paddingTop: 40 }}>
      {chill
        ? <img src="/kobo-chill.svg" width={300} height={220} style={{ maxWidth: '90%', height: 'auto' }}
            alt="Kobo relaxing in a deckchair with sunglasses, a gold chain and a glass of zobo" />
        : <Kobo mood="peek" size={110} />}
      <div className="eyebrow">{chill ? "Error 404 · Kobo's chill spot" : 'Error 404'}</div>
      <h1 className="h1" style={{ margin: 0 }}>{chill ? "Oops, you've landed in Kobo's chill spot" : "Kobo can't find this page"}</h1>
      <p className="muted" style={{ margin: 0 }}>
        {chill
          ? <>Not sure <b style={{ wordBreak: 'break-all' }}>{pathname}</b> is what you were looking for. Kobo's on a break here, but your drips aren't: everything still goes out on time.</>
          : <>There's nothing at <b style={{ wordBreak: 'break-all' }}>{pathname}</b>. The link may be old or mistyped. Your plans and money aren't affected.</>}
      </p>
      <div style={{ display: 'flex', gap: 8, width: '100%' }}>
        <button className="btn btn-soft" style={{ flex: 1 }} onClick={() => nav(-1)}>Go back</button>
        <button className="btn btn-primary" style={{ flex: 1 }} onClick={() => nav('/')}>Go to Home</button>
      </div>
    </div>
  );
}
