import { useEffect } from 'react';
import { useRive, useViewModelInstanceNumber } from '@rive-app/react-canvas';
import { RuntimeLoader } from '@rive-app/canvas';
import wasmUrl from '@rive-app/canvas/rive.wasm?url';
import type { KoboMood } from './Kobo';

// Ship the Rive engine with the app instead of fetching it from a public CDN.
RuntimeLoader.setWasmUrl(wasmUrl);

/** Order matches the `moodIndex` conditions in kobo.riv's state machine. */
export const MOOD_INDEX: Record<KoboMood, number> = {
  idle: 0, happy: 1, celebrate: 2, send: 3, fill: 4, waiting: 5, worried: 6, puddle: 7, sleep: 8, peek: 9,
};

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

  useEffect(() => { if (instance) setValue(MOOD_INDEX[mood]); }, [mood, instance, setValue]);

  return <RiveComponent style={{ width: size, height: size * 1.2 }} aria-hidden="true" />;
}
