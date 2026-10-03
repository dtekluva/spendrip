import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { N } from '../lib/format';
import { groupFeeTotal } from '../lib/fees';
import { useStore } from '../lib/store';
import type { DraftLine, Recipient } from '../lib/types';
import { AddRecipient } from '../screens/NewPlan';
import { Spinner } from './ui';

const MAX_PEOPLE = 50;
const naira = (s: string) => Math.round(Number(String(s).replace(/[₦,\s]/g, '')) * 100) || 0;
const toNaira = (k: number | null | undefined) => (k ? String(Math.round(k / 100)) : '');

/**
 * Who's on a group plan and how much each person gets. Three ways in (saved people, someone new, paste a list),
 * one-off changes per person (next payout only, or skip), and a footer that always shows the total with fees.
 */
export default function GroupEditor({ lines: start, onDone }: { lines: DraftLine[]; onDone: (lines: DraftLine[]) => void }) {
  const { recipients, me, summary } = useStore();
  const [lines, setLines] = useState<DraftLine[]>(start);
  const [mode, setMode] = useState<'' | 'saved' | 'new' | 'paste'>(start.length ? '' : 'saved');
  const [open, setOpen] = useState<number | null>(null);  // row whose "next payout" options are open
  const byId = (id: number) => recipients.find((r) => r.id === id);
  const maxEach = me?.user?.limits?.max_drip_kobo ?? null;
  const setLine = (i: number, patch: Partial<DraftLine>) => setLines((ls) => ls.map((l, j) => (j === i ? { ...l, ...patch } : l)));
  const add = (rs: Recipient[]) => setLines((ls) => [...ls, ...rs.filter((r) => !ls.some((l) => l.recipient_id === r.id))
    .map((r) => ({ recipient_id: r.id, amount_kobo: 0, next_amount_kobo: null, skip_next: false }))].slice(0, MAX_PEOPLE));

  const amounts = lines.map((l) => l.amount_kobo).filter((a) => a > 0);
  const total = amounts.reduce((t, a) => t + a, 0);
  const fees = groupFeeTotal(amounts, summary?.fees);
  const missing = lines.filter((l) => l.amount_kobo < 10_000).length;
  const over = maxEach ? lines.filter((l) => l.amount_kobo > maxEach || (l.next_amount_kobo ?? 0) > maxEach).length : 0;
  const allSkipped = lines.length > 0 && lines.every((l) => l.skip_next);
  const problem = lines.length < 2 ? 'Add at least 2 people.' : missing ? `Enter an amount for ${missing === 1 ? '1 person' : `${missing} people`} (₦100 or more).`
    : over ? `${over === 1 ? '1 amount is' : `${over} amounts are`} over your ${N(maxEach!)} per-transfer limit.`
    : allSkipped ? 'Everyone is skipped next time. Pause the plan instead.' : '';

  if (mode === 'saved') return <SavedPicker taken={lines.map((l) => l.recipient_id)} onBack={() => setMode('')} onNew={() => setMode('new')}
    onPick={(rs) => { add(rs); setMode(''); }} />;
  if (mode === 'new') return <><button className="link small" onClick={() => setMode('')}>← Back to the list</button>
    <AddRecipient onSaved={(r) => { add([r]); setMode(''); }} /></>;
  if (mode === 'paste') return <PasteList onBack={() => setMode('')} onAdd={(rows) => {
    setLines((ls) => [...ls.filter((l) => !rows.some((r) => r.recipient_id === l.recipient_id)), ...rows].slice(0, MAX_PEOPLE)); setMode('');
  }} />;

  return (
    <div className="group-ed">
      <h3>Who gets paid?</h3>
      <p className="small muted" style={{ marginTop: -6 }}>Everyone is paid together, at the same time. If your balance can't cover everyone, nobody is paid until it can.</p>
      <div className="g-rows">
        {lines.map((l, i) => {
          const r = byId(l.recipient_id);
          const tooBig = maxEach != null && l.amount_kobo > maxEach;
          return (
            <div key={l.recipient_id} className={`g-row ${l.skip_next ? 'skipped' : ''}`}>
              <span className={`tile sm t-${r?.is_self ? 'cobalt' : 'hibiscus'}`}>{r?.is_self ? '🙋' : (r?.label ?? '?')[0]}</span>
              <span className="g-who"><b>{r?.label ?? 'Someone'}</b>
                <span className="small muted">{r ? `${r.verified_account_name} · ${r.bank_name} ••${r.account_last4}` : ''}</span>
                {(l.skip_next || l.next_amount_kobo != null) && (
                  <span className="pill p-wait g-tag">{l.skip_next ? 'Skipped next time' : `${N(l.next_amount_kobo!)} next time only`}</span>)}
              </span>
              <label className={`g-amt ${tooBig ? 'bad' : ''}`}><span>₦</span>
                <input inputMode="numeric" aria-label={`Amount for ${r?.label}`} placeholder="0" value={toNaira(l.amount_kobo)}
                  onChange={(e) => setLine(i, { amount_kobo: naira(e.target.value.replace(/\D/g, '').slice(0, 8)) })} /></label>
              <button className="icon-btn g-more" aria-label={`More for ${r?.label}`} aria-expanded={open === i} onClick={() => setOpen(open === i ? null : i)}>⋯</button>
              {open === i && (
                <div className="g-opts">
                  <div className="field"><label htmlFor={`nx${i}`}>Next payout only (bonus or deduction)</label>
                    <input id={`nx${i}`} inputMode="numeric" placeholder={`Same as usual (₦${toNaira(l.amount_kobo) || 0})`} value={toNaira(l.next_amount_kobo)}
                      onChange={(e) => { const v = e.target.value.replace(/\D/g, ''); setLine(i, { next_amount_kobo: v ? naira(v) : null }); }} /></div>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    <button className="btn btn-soft" aria-pressed={l.skip_next} onClick={() => setLine(i, { skip_next: !l.skip_next })}>{l.skip_next ? '↩︎ Pay next time' : '⏭ Skip next payout'}</button>
                    <button className="btn btn-soft" style={{ color: 'var(--red)' }} onClick={() => { setLines((ls) => ls.filter((_, j) => j !== i)); setOpen(null); }}>Remove</button>
                  </div>
                  <p className="small muted" style={{ margin: 0 }}>One-off changes clear themselves after the next payout.</p>
                </div>
              )}
            </div>
          );
        })}
      </div>
      {lines.length < MAX_PEOPLE && (
        <div className="g-add">
          <button className="btn btn-soft" onClick={() => setMode('saved')}>＋ Saved people</button>
          <button className="btn btn-soft" onClick={() => setMode('new')}>＋ Someone new</button>
          <button className="btn btn-soft" onClick={() => setMode('paste')}>📋 Paste a list</button>
        </div>
      )}
      <div className="g-foot">
        <div className="kv"><span><b className="num">{lines.length}</b> {lines.length === 1 ? 'person' : 'people'} · <b className="num">{N(total)}</b></span>
          <span className="small muted num">+ {N(fees)} fees</span></div>
        <div className="small muted">{N(total + fees)} each payout. SpenDrip's fee is one {N(summary?.fees?.group_service_kobo ?? 10_000)} for the whole group; each transfer still has its own bank charge.</div>
        {problem && <div className="impact warn" style={{ marginTop: 8 }}>{problem}</div>}
        <button className="btn btn-primary btn-block" style={{ marginTop: 10 }} disabled={!!problem} onClick={() => onDone(lines)}>Done</button>
      </div>
    </div>
  );
}

function SavedPicker({ taken, onPick, onBack, onNew }: { taken: number[]; onPick: (rs: Recipient[]) => void; onBack: () => void; onNew: () => void }) {
  const { recipients } = useStore();
  const [sel, setSel] = useState<number[]>([]);
  const free = recipients.filter((r) => !taken.includes(r.id) && !r.label.endsWith('(removed)'));
  return (
    <>
      {taken.length > 0 && <button className="link small" onClick={onBack}>← Back to the list</button>}
      <h3>Pick people</h3>
      <div className="opt-list">
        {free.map((r) => {
          const on = sel.includes(r.id);
          return (
            <button key={r.id} className="opt" aria-pressed={on} onClick={() => setSel(on ? sel.filter((x) => x !== r.id) : [...sel, r.id])}>
              <span className={`tile sm t-${r.is_self ? 'cobalt' : 'hibiscus'}`}>{r.is_self ? '🙋' : r.label[0]}</span>
              <span><b>{r.label}</b><br /><span className="small muted">{r.bank_name} ••{r.account_last4}</span></span><span className="check">✓</span>
            </button>
          );
        })}
        <button className="opt" onClick={onNew}><span className="tile sm t-mint">＋</span><span><b>Someone new</b><br /><span className="small muted">Add their bank account</span></span><span /></button>
      </div>
      <button className="btn btn-primary btn-block" style={{ marginTop: 12 }} disabled={!sel.length}
        onClick={() => onPick(recipients.filter((r) => sel.includes(r.id)))}>Add {sel.length || ''} {sel.length === 1 ? 'person' : 'people'}</button>
    </>
  );
}

/* ---------------- paste a list ---------------- */

type Bank = { name: string; nip_code: string };
interface Row { line: string; name: string; account: string; bank?: Bank; amount: number; state: 'checking' | 'ok' | 'bad'; account_name?: string; error?: string }

const ALIASES: Record<string, string> = { gtb: 'gtbank', gtbank: 'gtbank', guaranty: 'gtbank', fbn: 'first bank', firstbank: 'first bank', uba: 'united bank',
  fcmb: 'first city', moniepoint: 'moniepoint', opay: 'opay', palmpay: 'palmpay', kuda: 'kuda', access: 'access', zenith: 'zenith', wema: 'wema', sterling: 'sterling' };

function findBank(text: string, banks: Bank[]): Bank | undefined {
  const t = text.toLowerCase().replace(/[^a-z ]/g, '').trim();
  if (!t) return undefined;
  const key = ALIASES[t.replace(/\s+bank$/, '').replace(/\s/g, '')] ?? t;
  return banks.find((b) => b.name.toLowerCase() === key) ?? banks.find((b) => b.name.toLowerCase().includes(key))
    ?? banks.find((b) => key.includes(b.name.toLowerCase().split(' ')[0]!));
}

/** "Musa, 0123456789, GTBank, 80000": the 10-digit number is the account, the bank is matched by name, the other number is the amount. */
function parse(line: string, banks: Bank[]): Omit<Row, 'state'> {
  // Split on commas, tabs, semicolons and bars, but not on thousands commas ("₦80,000").
  const parts = line.split(/[\t;|]+|,(?!\d{3}(?:\D|$))/).map((p) => p.trim()).filter(Boolean);
  let account = '', amount = 0, bank: Bank | undefined;
  const rest: string[] = [];
  for (const p of parts) {
    const digits = p.replace(/[₦,\s]/g, '');
    if (!account && /^\d{10}$/.test(digits)) account = digits;
    else if (!amount && /^\d+(\.\d+)?$/.test(digits)) amount = Math.round(Number(digits) * 100);
    else if (!bank && (bank = findBank(p, banks))) { /* matched */ }
    else rest.push(p);
  }
  return { line, name: rest.join(' ') || 'Someone', account, bank, amount };
}

function PasteList({ onBack, onAdd }: { onBack: () => void; onAdd: (lines: DraftLine[]) => void }) {
  const { recipients, reload } = useStore();
  const [banks, setBanks] = useState<Bank[]>([]);
  const [text, setText] = useState('');
  const [rows, setRows] = useState<Row[] | null>(null);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');
  useEffect(() => { api.get<Bank[]>('/banks').then(setBanks); }, []);

  const check = async () => {
    const parsed = text.split('\n').map((l) => l.trim()).filter(Boolean).slice(0, MAX_PEOPLE).map((l) => parse(l, banks));
    const start: Row[] = parsed.map((p) => ({ ...p, state: 'checking' }));
    setRows(start);
    const out = [...start];
    let next = 0;
    const worker = async () => {
      while (next < out.length) {
        const i = next++;
        const r = out[i]!;
        if (!r.account || !r.bank) out[i] = { ...r, state: 'bad', error: !r.account ? 'No 10-digit account number' : "Couldn't tell which bank" };
        else if (r.amount < 10_000) out[i] = { ...r, state: 'bad', error: 'No amount (₦100 or more)' };
        else {
          try {
            const res = await api.post<{ account_name: string }>('/recipients/lookup', { nip_bank_code: r.bank.nip_code, account_number: r.account });
            out[i] = { ...r, state: 'ok', account_name: res.account_name };
          } catch (e: any) { out[i] = { ...r, state: 'bad', error: e.message }; }
        }
        setRows([...out]);
      }
    };
    await Promise.all([worker(), worker(), worker()]);  // a few name checks at a time
  };

  const ok = rows?.filter((r) => r.state === 'ok') ?? [];
  const busy = rows?.some((r) => r.state === 'checking');
  const save = async () => {
    setSaving(true); setErr('');
    try {
      const lines: DraftLine[] = [];
      for (const r of ok) {
        const saved = recipients.find((x) => x.nip_bank_code === r.bank!.nip_code && x.account_last4 === r.account.slice(-4)
          && x.verified_account_name === r.account_name);
        let id = saved?.id;
        if (!id) {
          try { id = (await api.post<Recipient>('/recipients', { label: r.name.slice(0, 60), nip_bank_code: r.bank!.nip_code, account_number: r.account })).id; }
          catch (e: any) { throw new Error(`${r.name}: ${e.message}`); }
        }
        lines.push({ recipient_id: id, amount_kobo: r.amount, next_amount_kobo: null, skip_next: false });
      }
      await reload();
      onAdd(lines);
    } catch (e: any) { setErr(e.message); } finally { setSaving(false); }
  };

  return (
    <>
      <button className="link small" onClick={onBack}>← Back to the list</button>
      <h3>Paste a list</h3>
      {!rows ? (<>
        <p className="small muted" style={{ marginTop: -6 }}>One person per line: name, account number, bank, amount. Copy it from WhatsApp, Notes or a spreadsheet.</p>
        <textarea className="paste" rows={7} value={text} onChange={(e) => setText(e.target.value)} aria-label="List of people"
          placeholder={'Musa, 0123456789, GTBank, 80000\nBlessing, 9028906357, OPay, 70000\nEmeka, 2218840031, Access, 45000'} />
        <button className="btn btn-primary btn-block" style={{ marginTop: 10 }} disabled={!text.trim() || !banks.length} onClick={check}>Check names</button>
      </>) : (<>
        <div className="paste-rows">
          {rows.map((r, i) => (
            <div key={i} className={`paste-row ${r.state}`}>
              <span className="st" aria-hidden="true">{r.state === 'ok' ? '✓' : r.state === 'bad' ? '✗' : '…'}</span>
              <span style={{ minWidth: 0 }}><b>{r.name}</b> <span className="num">{r.amount ? N(r.amount) : ''}</span><br />
                <span className="small muted">{r.state === 'ok' ? `${r.account_name} · ${r.bank!.name} ••${r.account.slice(-4)}`
                  : r.state === 'bad' ? r.error : `${r.bank?.name ?? ''} ${r.account}`}</span></span>
            </div>
          ))}
        </div>
        {busy && <Spinner label="Checking names with the banks…" />}
        {!busy && rows.some((r) => r.state === 'bad') && <p className="small muted">Rows with ✗ won't be added. Fix them in your list and check again, or add them one by one.</p>}
        {err && <div className="error-card">{err}</div>}
        <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
          <button className="btn btn-soft" style={{ flex: 1 }} onClick={() => setRows(null)}>Edit list</button>
          <button className="btn btn-primary" style={{ flex: 2 }} disabled={busy || !ok.length || saving} onClick={save}>
            {saving ? 'Saving…' : `Add ${ok.length} ${ok.length === 1 ? 'person' : 'people'}`}</button>
        </div>
      </>)}
    </>
  );
}
