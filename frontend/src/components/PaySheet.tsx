import { useState } from 'react';
import { api } from '../lib/api';
import { useStore } from '../lib/store';
import Kobo from './Kobo';
import { useAction } from './ui';

/**
 * Take-home pay, used by Settings, Home and the prompt after someone's first plan.
 * `intro` is the friendlier first-time version ("How much of your pay is committed?") with a "Not now".
 */
export default function PaySheet({ intro = false, onSaved }: { intro?: boolean; onSaved?: () => void }) {
  const { me, closeSheet, toast, refreshMe, reload } = useStore();
  const [v, setV] = useState(me?.user?.salary_kobo ?? 0);
  const { busy, error, run } = useAction();
  const save = (value: number | null) => run(async () => {
    await api.put('/finance/profile', { salary_kobo: value });
    await Promise.all([refreshMe(), reload()]);
    closeSheet(); toast(value ? 'Take-home pay saved' : 'Take-home pay removed'); onSaved?.();
  });
  return (<>
    {intro && <div style={{ display: 'flex', justifyContent: 'center' }}><Kobo mood="happy" size={72} /></div>}
    <h3 style={intro ? { textAlign: 'center' } : undefined}>{intro ? 'How much of your pay is already planned?' : 'Your monthly take-home pay'}</h3>
    <p className="small muted" style={{ marginTop: -6, textAlign: intro ? 'center' : undefined }}>
      {intro ? "Add what lands in your account each month, and SpenDrip shows how much your plans commit from payday and how much is free to decide. Only you see it."
        : "What lands in your account each month after tax and deductions. Only you see it; it's used for your Finance report."}</p>
    <div className="field"><label htmlFor="pay-sheet">Take-home pay (₦)</label>
      <input id="pay-sheet" inputMode="numeric" value={v ? Math.round(v / 100).toLocaleString('en-NG') : ''} onChange={(e) => setV(Number(e.target.value.replace(/\D/g, '')) * 100)} autoFocus /></div>
    {error && <p className="err">{error}</p>}
    <div style={{ display: 'flex', gap: 8 }}>
      {intro ? <button className="btn btn-soft" disabled={busy} onClick={closeSheet}>Not now</button>
        : me?.user?.salary_kobo ? <button className="btn btn-soft" disabled={busy} onClick={() => save(null)}>Remove</button> : null}
      <button className="btn btn-primary" style={{ flex: 1 }} disabled={busy || v < 1_000_000} onClick={() => save(v)}>{intro ? 'Show me' : 'Save'}</button>
    </div>
  </>);
}
