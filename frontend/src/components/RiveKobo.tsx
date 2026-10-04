import { useEffect, useRef } from 'react';
import { useRive, useViewModelInstanceNumber } from '@rive-app/react-canvas';
import { RuntimeLoader } from '@rive-app/canvas';
import wasmUrl from '@rive-app/canvas/rive.wasm?url';
import type { KoboMood } from './Kobo';

// Ship the Rive engine with the app instead of fetching it from a public CDN.
RuntimeLoader.setWasmUrl(wasmUrl);

/** Order matches the `moodIndex` conditions in kobo.riv's state machine. */
export const MOOD_INDEX: Record<KoboMood, number> = {
  idle: 0, happy: 1, celebrate: 2, send: 3, fill: 4, waiting: 5, worried: 6, puddle: 7, sleep: 8, peek: 9,
  point: 10,
};

/** Moods where Kobo stands on his legs (shorts and trainers come with them). */
const LEG_MOODS = new Set<KoboMood>(['celebrate', 'send']);
const LIFT = -47;  // how far the body rises so the trainers rest on the ground
const STAND_MS = 220;

/** Kobo drawn and animated in Rive (public/kobo.riv). Each instance has its own mood. */
export default function RiveKobo({ mood, size, onReady }: { mood: KoboMood; size: number; onReady: () => void }) {
  const { rive, RiveComponent } = useRive({
    src: '/kobo.riv',
    artboard: 'Kobo',
    stateMachines: 'State Machine 1',
    autoplay: true,
    autoBind: true, // each Kobo has its own Rive instance, so the auto-bound instance is already per-Kobo
    onLoad: () => onReady(),
  });
  const instance = rive?.viewModelInstance ?? null;
  const { setValue } = useViewModelInstanceNumber('moodIndex', instance);
  const { setValue: setLookX } = useViewModelInstanceNumber('lookX', instance);
  const { setValue: setLookY } = useViewModelInstanceNumber('lookY', instance);
  const { setValue: setLegs } = useViewModelInstanceNumber('legs', instance);
  const { setValue: setLift } = useViewModelInstanceNumber('lift', instance);
  const box = useRef<HTMLSpanElement>(null);
  const standing = useRef(0);  // 0 = no legs, 1 = on his feet

  // Legs: ease up onto his feet as a leg mood starts, and back down after, instead of popping.
  useEffect(() => {
    if (!instance) return;
    const from = standing.current, to = LEG_MOODS.has(mood) ? 1 : 0;
    if (from === to) { setLegs(to); setLift(to * LIFT); return; }
    let raf = 0;
    const t0 = performance.now();
    const step = (now: number) => {
      const p = Math.min(1, (now - t0) / STAND_MS), e = p < 0.5 ? 2 * p * p : 1 - (-2 * p + 2) ** 2 / 2;
      const v = from + (to - from) * e;
      standing.current = v; setLegs(v); setLift(v * LIFT);
      if (p < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [mood, instance, setLegs, setLift]);

  useEffect(() => { if (instance) setValue(MOOD_INDEX[mood]); }, [mood, instance, setValue]);

  // Eyes follow the pointer (or a finger while it's on the screen): up to 8 units sideways and 6 up or down,
  // easing in over the first 300 px so a pointer right on Kobo doesn't make him go cross-eyed.
  useEffect(() => {
    if (!instance) return;
    let frame = 0, last: PointerEvent | null = null;
    const look = () => {
      frame = 0;
      const r = box.current?.getBoundingClientRect();
      if (!r || !last) return;
      const dx = last.clientX - (r.left + r.width / 2), dy = last.clientY - (r.top + r.height * 0.62);
      const d = Math.hypot(dx, dy) || 1, k = Math.min(1, d / 300);
      setLookX((dx / d) * 8 * k);
      setLookY((dy / d) * 6 * k);
    };
    const onMove = (e: PointerEvent) => { last = e; if (!frame) frame = requestAnimationFrame(look); };
    window.addEventListener('pointermove', onMove, { passive: true });
    return () => { window.removeEventListener('pointermove', onMove); if (frame) cancelAnimationFrame(frame); };
  }, [instance, setLookX, setLookY]);

  // The artboard (320×460) is bigger than Kobo's box (240×288 units) so jumps, sparkles and the flung droplet
  // aren't clipped. It overflows the box upwards and sideways, like the SVG version does.
  return (
    <span ref={box} style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
      <RiveComponent aria-hidden="true" style={{
        position: 'absolute', bottom: 0, left: '50%', transform: 'translateX(-50%)',
        width: size * (320 / 240), height: size * (460 / 240), pointerEvents: 'none',
      }} />
    </span>
  );
}
