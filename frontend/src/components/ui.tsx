import { useState, type ReactNode } from 'react';

export const DropSvg = () => <svg viewBox="0 0 40 52"><path d="M20 0S0 24 0 33a20 20 0 0 0 40 0C40 24 20 0 20 0z" /></svg>;

export function Wordmark({ className = 'brand-sm', style }: { className?: string; style?: React.CSSProperties }) {
  return <span className={`${className} wm`} style={style}>spendr<span className="i">ı<DropSvg /></span>p</span>;
}

export const Icon = {
  home: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"><path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" /></svg>,
  plans: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><rect x="3" y="4.5" width="18" height="16.5" rx="4" /><path d="M8 2.5v4M16 2.5v4M3 10h18M8 14.5h3M8 17.5h6" /></svg>,
  plus: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round"><path d="M12 5v14M5 12h14" /></svg>,
  activity: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 12h4l3-7 4 14 3-7h4" /></svg>,
  fund: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"><path d="M12 2.5S5 10.5 5 14.5a7 7 0 0 0 14 0c0-4-7-12-7-12z" /><path d="M12 11v6M9 14h6" strokeLinecap="round" /></svg>,
  calendar: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><rect x="3" y="4.5" width="18" height="16.5" rx="4" /><path d="M8 2.5v4M16 2.5v4M3 10h18" /><circle cx="8.5" cy="15" r="1" fill="currentColor" /><circle cx="12" cy="15" r="1" fill="currentColor" /></svg>,
  look: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="8.5" /><path d="M12 3.5a8.5 8.5 0 0 0 0 17z" fill="currentColor" /></svg>,
  bell: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M6 16V11a6 6 0 1 1 12 0v5l1.5 2h-15zM10 21h4" /></svg>,
  close: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round"><path d="M6 6l12 12M18 6 6 18" /></svg>,
  back: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M15 5l-7 7 7 7" /></svg>,
  face: <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M4 14V9a5 5 0 0 1 5-5h5M34 4h5a5 5 0 0 1 5 5v5M44 34v5a5 5 0 0 1-5 5h-5M14 44H9a5 5 0 0 1-5-5v-5" /><path d="M17 18v3M31 18v3M24 18v9h-2M18 33c3.5 3 8.5 3 12 0" /></svg>,
  check: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>,
  person: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4"><circle cx="12" cy="9" r="4.2" /><path d="M4.5 21c1.2-4 4.2-6 7.5-6s6.3 2 7.5 6" /></svg>,
};

export function Switch({ on, onChange, label, pri }: { on: boolean; onChange: () => void; label: string; pri?: boolean }) {
  return <button type="button" className={`switch ${pri ? 'pri' : ''}`} role="switch" aria-checked={on} aria-label={label}
    onClick={(e) => { e.stopPropagation(); onChange(); }} />;
}

const PILLS: Record<string, [string, string]> = {
  protected: ['p-prot', '🛡 Protected'], send: ['p-send', 'Will send'], wait: ['p-wait', 'Waits for top-up'], short: ['p-short', 'Short'],
  cap: ['p-wait', 'Over daily limit'], sent: ['p-send', '✓ Sent'], waited: ['p-wait', 'Waited'], failed: ['p-short', "Didn't go"],
  missed: ['p-wait', 'Missed'], paused: ['p-off', 'Paused'], sending: ['p-prot', 'Sending…'], scheduled: ['p-off', 'Scheduled'],
  received: ['p-send', 'Received'],
};
export const StatusPill = ({ status }: { status: string }) => {
  const [cls, label] = PILLS[status] ?? ['p-off', status];
  return <span className={`pill ${cls}`}>{label}</span>;
};

/** 4-digit PIN entry used by sign-up, sign-in, unlock and change PIN. */
export function PinPad({ value, onChange, extra, disabled }: { value: string; onChange: (v: string) => void; extra?: ReactNode; disabled?: boolean }) {
  const press = (k: string) => { if (disabled) return; if (k === 'del') onChange(value.slice(0, -1)); else if (value.length < 4) onChange(value + k); };
  return (
    <div className="pin-pad" data-no-replay="">
      {['1', '2', '3', '4', '5', '6', '7', '8', '9'].map((n) => <button key={n} type="button" onClick={() => press(n)}>{n}</button>)}
      {extra ?? <span />}
      <button type="button" onClick={() => press('0')}>0</button>
      <button type="button" className="ghost" aria-label="Delete" onClick={() => press('del')}>⌫</button>
    </div>
  );
}
export const PinDots = ({ n, bad }: { n: number; bad?: boolean }) => (
  <div className={`pin-dots ${bad ? 'bad' : ''}`}>{[0, 1, 2, 3].map((i) => <i key={i} className={i < n ? 'on' : ''} />)}</div>
);

export function Spinner({ label }: { label: string }) {
  return <div className="checking" style={{ justifyContent: 'center' }}><span className="spin" />{label}</div>;
}

/** Runs an async action with a busy flag and shows its error as a sentence. */
export function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const run = async <T,>(fn: () => Promise<T>): Promise<T | undefined> => {
    setBusy(true); setError('');
    try { return await fn(); } catch (e: any) { setError(e?.message ?? 'Something went wrong.'); return undefined; } finally { setBusy(false); }
  };
  return { busy, error, setError, run };
}
