import { useState, type ReactNode } from 'react';
import { useStore } from '../lib/store';
import Kobo, { type KoboMood } from './Kobo';

/**
 * A second check before actions that change what money goes out (pause, resume).
 * The safe choice is always on the left and closes the sheet (or goes back, via onStop).
 */
export function Confirm({ mood = 'waiting', title, body, yes, no, danger, onYes, onStop }: {
  mood?: KoboMood; title: string; body: ReactNode; yes: string; no: string; danger?: boolean;
  onYes: () => Promise<unknown> | void; onStop?: () => void;
}) {
  const { closeSheet } = useStore();
  const [busy, setBusy] = useState(false);
  const stop = () => (onStop ? onStop() : closeSheet());
  return (
    <div className="stack" style={{ alignItems: 'center', textAlign: 'center', gap: 10 }}>
      <Kobo mood={mood} size={84} />
      <h3 style={{ margin: 0 }}>{title}</h3>
      <div className="muted" style={{ margin: 0 }}>{body}</div>
      <div style={{ display: 'flex', gap: 8, width: '100%', marginTop: 6 }}>
        <button className="btn btn-soft" style={{ flex: 1 }} disabled={busy} onClick={stop}>{no}</button>
        <button className={`btn ${danger ? 'btn-danger' : 'btn-primary'}`} style={{ flex: 1 }} disabled={busy}
          onClick={async () => { setBusy(true); try { await onYes(); } finally { setBusy(false); } }}>{yes}</button>
      </div>
    </div>
  );
}
