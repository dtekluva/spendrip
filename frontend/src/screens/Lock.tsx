import { useState } from 'react';
import { api } from '../lib/api';
import { getPasskey, passkeysSupported } from '../lib/passkey';
import { useStore } from '../lib/store';
import type { Me } from '../lib/types';
import { Icon, PinDots, PinPad, Spinner, Wordmark, useAction } from '../components/ui';
import Kobo from '../components/Kobo';

/** Returning on the same device: Face ID, or the PIN. */
export default function Lock({ onUnlocked, onForgot }: { onUnlocked: (m: Me) => void; onForgot: () => void }) {
  const { me, refreshMe } = useStore();
  const signOut = async () => { await api.post('/auth/signout'); await refreshMe(); };
  const canFace = !!me?.user?.has_face_id && passkeysSupported();
  const [mode, setMode] = useState<'face' | 'pin'>(canFace ? 'face' : 'pin');
  const [pin, setPin] = useState('');
  const [scanning, setScanning] = useState(false);
  const { busy, error, setError, run } = useAction();

  const face = () => run(async () => {
    setScanning(true);
    try {
      const opts = await api.post<any>('/auth/passkey/unlock/options');
      onUnlocked(await api.post<Me>('/auth/passkey/unlock/verify', { credential: await getPasskey(opts) }));
    } catch (e: any) {
      if (e?.name === 'NotAllowedError') { setMode('pin'); return; }
      throw e;
    } finally { setScanning(false); }
  });
  const change = (v: string) => {
    setPin(v); setError('');
    if (v.length === 4) window.setTimeout(() => run(async () => {
      try { onUnlocked(await api.post<Me>('/auth/unlock', { pin: v })); }
      catch (e: any) { setPin(''); if (e.code === 'pin_locked') onForgot(); throw e; }
    }), 150);
  };

  return (
    <div className="lock">
      <Wordmark style={{ marginBottom: 6 }} />
      <Kobo mood={error ? 'puddle' : 'peek'} size={64} follow />
      <h2>Welcome back{me?.user?.first_name ? `, ${me.user.first_name}` : ''} 👋</h2>
      {me?.user?.phone_masked && <p className="small muted" style={{ margin: '-6px 0 0' }}>{me.user.phone_masked}</p>}
      {mode === 'face' ? (
        <>
          <div className={`face-ic ${scanning ? 'scan' : ''}`}>{Icon.face}</div>
          {error && <div className="error-card">{error}</div>}
          <div className="kyc-actions" style={{ width: '100%', maxWidth: 340 }}>
            <button className="btn btn-primary btn-block" style={{ height: 56 }} onClick={face} disabled={scanning}>Unlock with Face ID</button>
            <button className="btn btn-soft btn-block" onClick={() => setMode('pin')}>Use PIN instead</button>
          </div>
        </>
      ) : (
        <>
          <p className="muted" style={{ margin: 0 }}>Enter your PIN</p>
          <PinDots n={pin.length} bad={!!error} />
          {busy ? <Spinner label="Unlocking…" /> : <p className="err">{error}</p>}
          <PinPad value={pin} onChange={change} disabled={busy}
            extra={canFace ? <button className="ghost" aria-label="Use Face ID" onClick={() => { setMode('face'); face(); }}>Face ID</button> : undefined} />
          <button className="link small" style={{ marginTop: 6 }} onClick={onForgot}>Forgot PIN?</button>
        </>
      )}
      <button className="link small" style={{ marginTop: 'auto', color: 'var(--muted)' }} onClick={signOut}>Not you? Sign out</button>
    </div>
  );
}
