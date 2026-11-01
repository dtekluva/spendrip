import { useState, type ReactNode } from 'react';
import { Ic } from '../icons';

export const DropSvg = () => <svg viewBox="0 0 40 52"><path d="M20 0S0 24 0 33a20 20 0 0 0 40 0C40 24 20 0 20 0z" /></svg>;

export function Wordmark({ className = 'brand-sm', style }: { className?: string; style?: React.CSSProperties }) {
  return <span className={`${className} wm`} style={style}>spendr<span className="i">ı<DropSvg /></span>p</span>;
}

/** The app's common UI icons, as ready-made elements (see src/icons for the full set). */
export const Icon = {
  home: <Ic name="home" />,
  plans: <Ic name="plans" />,
  plus: <Ic name="plus" />,
  activity: <Ic name="activity" />,
  fund: <Ic name="fund" />,
  calendar: <Ic name="calendar" />,
  look: <Ic name="appearance" />,
  bell: <Ic name="bell" />,
  close: <Ic name="close" />,
  back: <Ic name="back" />,
  face: <Ic name="face" />,
  check: <Ic name="check" />,
  finance: <Ic name="finance" />,
  gear: <Ic name="settings" />,
  person: <Ic name="profile" />,
};

export function Switch({ on, onChange, label, pri }: { on: boolean; onChange: () => void; label: string; pri?: boolean }) {
  return <button type="button" className={`switch ${pri ? 'pri' : ''}`} role="switch" aria-checked={on} aria-label={label}
    onClick={(e) => { e.stopPropagation(); onChange(); }} />;
}

const PILLS: Record<string, [string, ReactNode]> = {
  protected: ['p-prot', <><Ic name="protected" />Protected</>], send: ['p-send', 'Will send'], wait: ['p-wait', 'Waits for top-up'], short: ['p-short', 'Short'],
  cap: ['p-wait', 'Over daily limit'], sent: ['p-send', <><Ic name="check" />Sent</>], waited: ['p-wait', 'Waited'], failed: ['p-short', "Didn't go"],
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
      <button type="button" className="ghost" aria-label="Delete" onClick={() => press('del')}><Ic name="backspace" /></button>
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
