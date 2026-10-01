import { useEffect } from 'react';
import { DropSvg } from '../components/ui';

/** Drop falls, ripples, the wordmark rises and the drop lands as the dot on the i. */
export default function Splash({ onDone, quick }: { onDone: () => void; quick: boolean }) {
  useEffect(() => {
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const t = window.setTimeout(onDone, reduce ? 700 : quick ? 1500 : 2900);
    return () => window.clearTimeout(t);
  }, [onDone, quick]);
  const letters = ['s', 'p', 'e', 'n', 'd', 'r', 'ı', 'p'];
  return (
    <div className="splash" aria-label="SpenDrip" onClick={onDone}>
      <div className="blob b1" /><div className="blob b2" />
      <div className="stagewrap">
        <svg className="fall" viewBox="0 0 40 52"><path d="M20 0S0 24 0 33a20 20 0 0 0 40 0C40 24 20 0 20 0z" /></svg>
        <div className="ripple" /><div className="ripple r2" />
        <div className="word wm" aria-hidden="true">
          {letters.map((l, i) => (
            <span key={i} className={l === 'ı' ? 'i' : ''} style={{ animationDelay: `${0.72 + i * 0.06}s` }}>{l}{l === 'ı' && <DropSvg />}</span>
          ))}
        </div>
      </div>
      <div className="tag">Money that shows up on time.</div>
      <button className="skip">Tap to skip</button>
    </div>
  );
}
