import { useLocation, useNavigate } from 'react-router-dom';
import Kobo from '../components/Kobo';

/** Any address inside the app that doesn't exist. */
export default function NotFound() {
  const nav = useNavigate();
  const { pathname } = useLocation();
  return (
    <div className="stack" style={{ alignItems: 'center', textAlign: 'center', maxWidth: 460, margin: '0 auto', paddingTop: 40 }}>
      <Kobo mood="peek" size={110} />
      <div className="eyebrow">Error 404</div>
      <h1 className="h1" style={{ margin: 0 }}>Kobo can't find this page</h1>
      <p className="muted" style={{ margin: 0 }}>There's nothing at <b style={{ wordBreak: 'break-all' }}>{pathname}</b>. The link may be old or mistyped. Your plans and money aren't affected.</p>
      <div style={{ display: 'flex', gap: 8, width: '100%' }}>
        <button className="btn btn-soft" style={{ flex: 1 }} onClick={() => nav(-1)}>Go back</button>
        <button className="btn btn-primary" style={{ flex: 1 }} onClick={() => nav('/')}>Go to Home</button>
      </div>
    </div>
  );
}
