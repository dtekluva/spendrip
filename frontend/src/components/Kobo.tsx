import { Component, lazy, Suspense, useEffect, useId, useRef, useState, type ReactNode } from 'react';

// The Rive version loads lazily (its engine is ~2 MB); the SVG Kobo shows instantly and stays as the fallback.
const RiveKobo = lazy(() => import('./RiveKobo'));
const reducedMotion = () => typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;
let riveBroken = false;

/**
 * Kobo, the SpenDrip drop. Pure SVG + CSS, so it costs nothing to load.
 * When the Rive version arrives it can replace this component with the same `mood` names.
 */
export type KoboMood =
  | 'idle' // gentle bob and blink
  | 'happy' // bouncing with a big smile
  | 'celebrate' // big jump with sparkles
  | 'waiting' // sways, glances, "…" bubble
  | 'worried' // shrinks a little, brows up, sweat drop
  | 'puddle' // splats flat, then pops back up
  | 'send' // a droplet leaves its head and flies off
  | 'fill' // fills up and grows
  | 'sleep' // eyes shut, breathing, z z
  | 'peek'; // rises into view and blinks

export const KOBO_MOODS: { mood: KoboMood; label: string; when: string }[] = [
  { mood: 'idle', label: 'Idle', when: 'Home, nothing to do' },
  { mood: 'happy', label: 'Happy', when: 'Month is covered' },
  { mood: 'celebrate', label: 'Celebrate', when: 'Plan created, fully funded, verified' },
  { mood: 'send', label: 'Sending', when: 'A drip just went out' },
  { mood: 'fill', label: 'Filling up', when: 'Money was added' },
  { mood: 'waiting', label: 'Waiting', when: 'A drip is waiting for a top-up' },
  { mood: 'worried', label: 'Worried', when: 'Priorities are short' },
  { mood: 'puddle', label: 'Oops', when: 'Something went wrong' },
  { mood: 'sleep', label: 'Asleep', when: 'Everything is paused' },
  { mood: 'peek', label: 'Peek', when: 'Lock screen, empty states' },
];

const BODY = 'M50 6C50 6 13 55 13 79a37 37 0 0 0 74 0C87 55 50 6 50 6Z';

export default function Kobo({ mood = 'idle', size = 72, follow = false, title, engine = 'auto' }: {
  mood?: KoboMood; size?: number; follow?: boolean; title?: string;
  /** auto: Rive when possible. Force 'svg' or 'rive' to compare the two (Meet Kobo page). */
  engine?: 'auto' | 'rive' | 'svg';
}) {
  const [riveReady, setRiveReady] = useState(false);
  // Eyes that follow your finger exist only in the SVG version, so Kobos with `follow` stay SVG.
  const showRive = engine === 'rive' || (engine === 'auto' && !follow && !riveBroken && !reducedMotion());
  if (showRive) {
    return (
      <span className="kobo kobo-rive" style={{ width: size, height: size * 1.2, position: 'relative' }} role="img" aria-label={title ?? `Kobo, ${mood}`}>
        {!riveReady && <SvgKobo mood={mood} size={size} />}
        <Suspense fallback={null}>
          <RiveBoundary onFail={() => { riveBroken = true; }}>
            <span style={{ position: 'absolute', inset: 0, opacity: riveReady ? 1 : 0 }}>
              <RiveKobo mood={mood} size={size} onReady={() => setRiveReady(true)} />
            </span>
          </RiveBoundary>
        </Suspense>
      </span>
    );
  }
  return <SvgKobo mood={mood} size={size} follow={follow} title={title} />;
}

/** Which engine `<Kobo>` will use with these settings, for labels. */
export const koboEngine = (follow = false) => (!follow && !riveBroken && !reducedMotion() ? 'Rive' : 'Code');

class RiveBoundary extends Component<{ onFail: () => void; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch() { this.props.onFail(); }
  render() { return this.state.failed ? null : this.props.children; }
}

function SvgKobo({ mood = 'idle', size = 72, follow = false, title }: {
  mood?: KoboMood; size?: number; follow?: boolean; title?: string;
}) {
  const ref = useRef<SVGSVGElement>(null);
  const uid = 'k' + useId().replace(/[^a-zA-Z0-9]/g, ''); // unique gradient/clip ids per instance
  const [look, setLook] = useState({ x: 0, y: 0 });

  // Eyes follow the pointer (or finger) a little.
  useEffect(() => {
    if (!follow) return;
    const onMove = (e: PointerEvent) => {
      const r = ref.current?.getBoundingClientRect();
      if (!r) return;
      const dx = e.clientX - (r.left + r.width / 2), dy = e.clientY - (r.top + r.height * 0.62);
      const d = Math.hypot(dx, dy) || 1;
      const k = Math.min(1, d / 240);
      setLook({ x: (dx / d) * 3 * k, y: (dy / d) * 2.5 * k });
    };
    window.addEventListener('pointermove', onMove);
    return () => window.removeEventListener('pointermove', onMove);
  }, [follow]);

  const happyEyes = mood === 'happy' || mood === 'celebrate' || mood === 'fill';
  const closedEyes = mood === 'sleep';
  const mouth = {
    idle: 'M43 90q7 5 14 0',
    happy: 'M40 88q10 11 20 0Z',
    celebrate: 'M39 87q11 13 22 0Z',
    send: 'M43 90q7 5 14 0',
    fill: 'M41 88q9 9 18 0Z',
    waiting: 'M44 92h12',
    worried: 'M42 93q4-4 8 0t8 0',
    puddle: 'M44 92q6-4 12 0',
    sleep: 'M46 92q4 2 8 0',
    peek: 'M44 90q6 4 12 0',
  }[mood];
  const filled = mouth.endsWith('Z');

  return (
    <span className={`kobo kobo-${mood}`} style={{ width: size, height: size * 1.2 }} role="img" aria-label={title ?? `Kobo, ${mood}`}>
      <svg ref={ref} viewBox="0 0 100 120" width={size} height={size * 1.2} overflow="visible">
        <defs>
          <radialGradient id={`${uid}-shade`} cx="38%" cy="42%" r="70%">
            <stop offset="0" stopColor="#FFE47A" />
            <stop offset="0.55" stopColor="#FFD23F" />
            <stop offset="1" stopColor="#F2B400" />
          </radialGradient>
          <clipPath id={`${uid}-clip`}><path d={BODY} /></clipPath>
        </defs>

        <ellipse className="k-shadow" cx="50" cy="116" rx="26" ry="4" />

        <g className="k-extras">
          {mood === 'celebrate' && [0, 1, 2, 3, 4, 5].map((i) => (
            <path key={i} className="k-spark" style={{ ['--a' as any]: `${i * 60}deg`, animationDelay: `${i * 0.05}s` }}
              d="M50 0l2.4 5.6L58 8l-5.6 2.4L50 16l-2.4-5.6L42 8l5.6-2.4Z" transform="translate(0 52)" />
          ))}
          {mood === 'waiting' && <g className="k-bubble"><rect x="70" y="18" width="30" height="18" rx="9" /><circle cx="78" cy="27" r="2.2" /><circle cx="85" cy="27" r="2.2" /><circle cx="92" cy="27" r="2.2" /></g>}
          {mood === 'sleep' && <g className="k-z"><text x="74" y="34">z</text><text x="84" y="22">z</text></g>}
          {mood === 'send' && <path className="k-droplet" d="M50 0C50 0 43 9 43 13a7 7 0 0 0 14 0C57 9 50 0 50 0Z" />}
          {mood === 'worried' && <path className="k-sweat" d="M80 52c0 0-5 7-5 10a5 5 0 0 0 10 0c0-3-5-10-5-10Z" />}
        </g>

        <g className="k-body">
          <path d={BODY} fill={`url(#${uid}-shade)`} className="k-skin" />
          {mood === 'fill' && <g clipPath={`url(#${uid}-clip)`}><rect className="k-level" x="0" y="40" width="100" height="90" /></g>}
          <ellipse cx="34" cy="58" rx="6" ry="10" className="k-shine" transform="rotate(25 34 58)" />
          <ellipse cx="29" cy="92" rx="6" ry="3.6" className="k-cheek" />
          <ellipse cx="71" cy="92" rx="6" ry="3.6" className="k-cheek" />

          {mood === 'worried' && <g className="k-brows"><path d="M32 66l9-4" /><path d="M68 66l-9-4" /></g>}

          <g className="k-eyes" style={{ transform: `translate(${look.x}px, ${look.y}px)` }}>
            {happyEyes ? (
              <g className="k-arc"><path d="M33 79q5-7 10 0" /><path d="M57 79q5-7 10 0" /></g>
            ) : closedEyes ? (
              <g className="k-arc"><path d="M33 78q5 4 10 0" /><path d="M57 78q5 4 10 0" /></g>
            ) : (
              <g className="k-open">
                <ellipse cx="38" cy="77" rx="5" ry="7" className="k-eye" />
                <ellipse cx="62" cy="77" rx="5" ry="7" className="k-eye" />
                <circle cx="39.6" cy="74" r="1.8" className="k-glint" />
                <circle cx="63.6" cy="74" r="1.8" className="k-glint" />
              </g>
            )}
          </g>
          <path d={mouth} className={filled ? 'k-mouth filled' : 'k-mouth'} />
        </g>
      </svg>
    </span>
  );
}

/** A short pop-up moment: Kobo plus a one-line speech bubble, e.g. after creating a plan. */
export function KoboMoment({ mood, text }: { mood: KoboMood; text: string }) {
  return (
    <div className="kobo-pop" role="status">
      <Kobo mood={mood} size={56} />
      <span className="kobo-say">{text}</span>
    </div>
  );
}
