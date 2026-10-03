import { useEffect, useId, useRef, useState } from 'react';

export interface Bank { name: string; nip_code: string }

const ALIASES: Record<string, string[]> = {
  gtbank: ['gtb', 'guaranty', 'gt bank'], 'first bank': ['fbn', 'firstbank'], uba: ['united bank for africa'], fcmb: ['first city'],
  'access bank': ['diamond'], 'stanbic ibtc': ['stanbic'], 'standard chartered': ['stanchart'], 'mtn momo psb': ['momo', 'mtn'],
  'smartcash psb (airtel)': ['airtel', 'smartcash'], 'titan trust bank': ['titan'], 'vfd microfinance bank': ['vfd', 'v bank', 'vbank'],
};

const matches = (b: Bank, q: string) => {
  const name = b.name.toLowerCase();
  return name.includes(q) || (ALIASES[name] ?? []).some((a) => a.includes(q) || q.includes(a));
};

/**
 * Type to find a bank or wallet; pick from the matches. Keyboard: arrows move, Enter picks, Escape closes.
 * Holds the NIP code as its value, like the <select> it replaces.
 */
export default function BankPicker({ banks, value, onChange, id }: { banks: Bank[]; value: string; onChange: (nip: string) => void; id?: string }) {
  const listId = useId();
  const chosen = banks.find((b) => b.nip_code === value);
  const [text, setText] = useState(chosen?.name ?? '');
  const [open, setOpen] = useState(false);
  const [hi, setHi] = useState(0);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => { if (chosen && !open) setText(chosen.name); }, [chosen?.nip_code]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const away = (e: PointerEvent) => { if (!box.current?.contains(e.target as Node)) { setOpen(false); setText(chosen?.name ?? ''); } };
    document.addEventListener('pointerdown', away);
    return () => document.removeEventListener('pointerdown', away);
  }, [chosen]);

  const q = text.trim().toLowerCase();
  const shown = (open ? (q && text !== chosen?.name ? banks.filter((b) => matches(b, q)) : banks) : []).slice(0, 12);
  const pick = (b: Bank) => { onChange(b.nip_code); setText(b.name); setOpen(false); };
  const onKey = (e: React.KeyboardEvent) => {
    if (!open && (e.key === 'ArrowDown' || e.key === 'Enter')) { setOpen(true); return; }
    if (e.key === 'ArrowDown') { e.preventDefault(); setHi((h) => Math.min(h + 1, shown.length - 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setHi((h) => Math.max(h - 1, 0)); }
    else if (e.key === 'Enter') { e.preventDefault(); if (shown[hi]) pick(shown[hi]!); }
    else if (e.key === 'Escape') { setOpen(false); setText(chosen?.name ?? ''); }
  };

  return (
    <div className="bank-pick" ref={box}>
      <input id={id} role="combobox" aria-expanded={open} aria-controls={listId} aria-autocomplete="list" autoComplete="off"
        placeholder="Type a bank or wallet, e.g. OPay" value={text}
        onFocus={() => { setOpen(true); setHi(0); }}
        onChange={(e) => { setText(e.target.value); setOpen(true); setHi(0); if (chosen) onChange(''); }}
        onKeyDown={onKey} />
      {chosen && !open && <span className="bank-ok" aria-hidden="true">✓</span>}
      {open && (
        <ul id={listId} role="listbox" className="bank-list">
          {shown.map((b, i) => (
            <li key={b.nip_code} role="option" aria-selected={i === hi} className={i === hi ? 'hi' : ''}
              onPointerDown={(e) => { e.preventDefault(); pick(b); }} onPointerEnter={() => setHi(i)}>{b.name}</li>
          ))}
          {!shown.length && <li className="none">No bank matches "{text}". Try another spelling.</li>}
        </ul>
      )}
    </div>
  );
}
