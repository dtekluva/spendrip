import { useEffect, useState } from 'react';

/** Kobo's seasonal outfit (set in the admin under Seasons). Keys match the switches in public/kobo.riv. */
export const OUTFITS = ['xmas', 'newyear', 'love', 'mama', 'sallah', 'easter', 'naija',
  'halloween', 'thanksgiving', 'stpatrick', 'usmom', 'juneteenth', 'july4'] as const;
export type Outfit = typeof OUTFITS[number];

let current: Outfit | null = null;
let checkedAt = 0;
const listeners = new Set<(o: Outfit | null) => void>();

/** Asks the API which outfit is on. At most once an hour, plus when the app comes back to the foreground. */
async function refresh(force = false) {
  if (!force && Date.now() - checkedAt < 60 * 60 * 1000) return;
  checkedAt = Date.now();
  try {
    const r = await fetch('/api/season', { credentials: 'omit' });
    if (!r.ok) return;
    const { outfit } = await r.json() as { outfit: string | null };
    const next = OUTFITS.includes(outfit as Outfit) ? outfit as Outfit : null;
    if (next !== current) { current = next; listeners.forEach((l) => l(current)); }
  } catch { /* offline: keep what we had */ }
}

if (typeof window !== 'undefined') {
  refresh(true);
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') refresh(); });
}

export function useOutfit(): Outfit | null {
  const [o, setO] = useState(current);
  useEffect(() => { listeners.add(setO); setO(current); return () => { listeners.delete(setO); }; }, []);
  return o;
}
