import type { Look } from '../lib/types';

const LOOKS: [Look, string, string][] = [['themed', 'Themed', 'Bold and colourful'], ['light', 'Light', 'Clean and bright'], ['dark', 'Dark', 'Easy on the eyes']];

function AppearanceSheet({ current, onPick }: { current: Look; onPick: (l: Look) => void }) {
  return (
    <>
      <h3>Appearance</h3>
      <div className="look-opts">
        {LOOKS.map(([k, l, d]) => (
          <button key={k} className="look-opt" aria-pressed={current === k} onClick={() => onPick(k)}>
            <span className="look-prev" data-look={k}><span className="mini-hero"><span className="mini-bar"><i /><i /></span></span>
              <span className="mini-row" /><span className="mini-row" /><span className="mini-btn2" /></span>
            <span>{l}<br /><span className="small muted" style={{ fontWeight: 600 }}>{d}</span></span>
          </button>
        ))}
      </div>
      <p className="small muted" style={{ margin: '14px 0 0' }}>You can change this any time from Home or Profile.</p>
    </>
  );
}

export function openAppearance(store: { look: Look; setLook: (l: Look) => void; openSheet: (n: React.ReactNode) => void; toast: (m: string) => void }) {
  const pick = (l: Look) => { store.setLook(l); store.openSheet(<AppearanceSheet current={l} onPick={pick} />); store.toast(`${LOOKS.find((x) => x[0] === l)![1]} look on`); };
  store.openSheet(<AppearanceSheet current={store.look} onPick={pick} />);
}
