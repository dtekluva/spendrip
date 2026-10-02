import { useEffect } from 'react';
import { DropSvg } from '../components/ui';

const BODY = 'M50 6C50 6 13 55 13 79a37 37 0 0 0 74 0C87 55 50 6 50 6Z';
// Splash droplets thrown out when Kobo lands: [x distance, peak height, size]
const DROPS: [number, number, number][] = [[-58, 34, 9], [-34, 52, 7], [-14, 40, 5], [16, 44, 6], [38, 56, 8], [60, 30, 6]];

/** Kobo falls, splats (ripples + droplets), bounces up smiling; the wordmark rises under it and the i gets its dot. */
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
        <div className="sk-wrap" aria-hidden="true">
          <div className="sk-glow" />
          <div className="ripple" /><div className="ripple r2" />
          {DROPS.map(([x, h, s], i) => (
            <span key={i} className="sk-drop" style={{ ['--x' as any]: `${x}px`, ['--h' as any]: `${-h}px`, width: s, height: s * 1.25, animationDelay: `${0.5 + i * 0.015}s` }} />
          ))}
          <div className="sk-hop">
            <svg className="sk" viewBox="0 0 100 120">
              <defs>
                <radialGradient id="sk-shade" cx="38%" cy="42%" r="70%">
                  <stop offset="0" stopColor="#FFE47A" /><stop offset=".55" stopColor="#FFD23F" /><stop offset="1" stopColor="#F2B400" />
                </radialGradient>
              </defs>
              <g className="sk-body">
                <path d={BODY} fill="url(#sk-shade)" stroke="#E0A400" strokeWidth="1.5" />
                <ellipse cx="34" cy="58" rx="6" ry="10" fill="#fff" opacity=".55" transform="rotate(25 34 58)" />
                <ellipse cx="29" cy="92" rx="6" ry="3.6" fill="#FF4F8B" opacity=".35" />
                <ellipse cx="71" cy="92" rx="6" ry="3.6" fill="#FF4F8B" opacity=".35" />
                <g className="sk-open">
                  <g className="sk-blink">
                    <ellipse cx="38" cy="77" rx="5" ry="7" fill="#0E1233" /><ellipse cx="62" cy="77" rx="5" ry="7" fill="#0E1233" />
                    <circle cx="39.6" cy="74" r="1.8" fill="#fff" /><circle cx="63.6" cy="74" r="1.8" fill="#fff" />
                  </g>
                </g>
                <g className="sk-happy" fill="none" stroke="#0E1233" strokeWidth="3.4" strokeLinecap="round">
                  <path d="M33 79q5-7 10 0" /><path d="M57 79q5-7 10 0" />
                </g>
                <ellipse className="sk-o" cx="50" cy="91" rx="4" ry="5" fill="#0E1233" />
                <path className="sk-smile" d="M40 88q10 11 20 0Z" fill="#0E1233" />
              </g>
            </svg>
          </div>
        </div>
        <div className="word wm" aria-hidden="true">
          {letters.map((l, i) => (
            <span key={i} className={l === 'ı' ? 'i' : ''} style={{ animationDelay: `${0.78 + i * 0.05}s` }}>{l}{l === 'ı' && <DropSvg />}</span>
          ))}
        </div>
      </div>
      <div className="tag">Money that shows up on time.</div>
      <button className="skip">Tap to skip</button>
    </div>
  );
}
