import { useState } from 'react';
import { DAY_FROM, NIGHT_FROM, resolveLook } from '../lib/store';
import type { Look } from '../lib/types';

const hour = (h: number) => `${h % 12 || 12} ${h < 12 ? 'AM' : 'PM'}`;

/** [key, name, one-line summary, what it means (shown on the ⓘ)] */
const LOOKS: [Look, string, string, string][] = [
  ['auto', 'Time-aware', 'Light by day, dark by night',
    `Follows your phone's clock: Light from ${hour(DAY_FROM)} to ${hour(NIGHT_FROM)}, Dark from ${hour(NIGHT_FROM)} to ${hour(DAY_FROM)}. It switches by itself; nothing to do.`],
  ['themed', 'Themed', 'Bold and colourful', "SpenDrip's own colours, deep blue and yellow, at every hour of the day."],
  ['light', 'Light', 'Clean and bright', 'A bright background with dark text. Best in daylight and bright rooms.'],
  ['dark', 'Dark', 'Easy on the eyes', 'A dark background with soft text. Kinder on the eyes at night, and uses less battery on most phone screens.'],
];
export const lookName = (l: Look) => LOOKS.find((x) => x[0] === l)?.[1] ?? l;

function AppearanceSheet({ current, onPick }: { current: Look; onPick: (l: Look) => void }) {
  const [hint, setHint] = useState<Look | null>(null);  // the ⓘ that's open; one at a time
  const now = resolveLook('auto');
  return (
    <>
      <h3>Appearance</h3>
      <div className="look-opts">
        {LOOKS.map(([k, l, d, about]) => (
          <div key={k} className="look-cell">
            <button className="look-opt" aria-pressed={current === k} onClick={() => onPick(k)}>
              <span className="look-prev" data-look={k === 'auto' ? now : k}>
                {k === 'auto' && <span className="look-badge" aria-hidden="true">{now === 'light' ? '☀️' : '🌙'}</span>}
                <span className="mini-hero"><span className="mini-bar"><i /><i /></span></span>
                <span className="mini-row" /><span className="mini-row" /><span className="mini-btn2" />
              </span>
              <span>{l}<br /><span className="small muted" style={{ fontWeight: 600 }}>{d}</span></span>
            </button>
            <button className="look-info" aria-label={`About ${l}`} aria-expanded={hint === k} aria-controls={`look-hint-${k}`}
              onClick={() => setHint(hint === k ? null : k)}>i</button>
            {hint === k && <p id={`look-hint-${k}`} className="look-hint" role="note">{about}</p>}
          </div>
        ))}
      </div>
      <p className="small muted" style={{ margin: '14px 0 0' }}>Tap <b>i</b> to see what each one does. You can change this any time from Home or Profile.</p>
    </>
  );
}

export function openAppearance(store: { look: Look; setLook: (l: Look) => void; openSheet: (n: React.ReactNode) => void; toast: (m: string) => void }) {
  const pick = (l: Look) => {
    store.setLook(l);
    store.openSheet(<AppearanceSheet current={l} onPick={pick} />);
    store.toast(l === 'auto' ? `Time-aware on: ${lookName(resolveLook('auto'))} for now` : `${lookName(l)} look on`);
  };
  store.openSheet(<AppearanceSheet current={store.look} onPick={pick} />);
}
