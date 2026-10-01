import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../lib/api';
import { N } from '../lib/format';
import { useStore } from '../lib/store';
import Kobo from '../components/Kobo';
import { Spinner, useAction } from '../components/ui';

export interface SavedCard { id: number; brand: string; last4: string; bank: string; exp: string }
interface Quote { available: boolean; test_mode: boolean; net_kobo: number; fee_kobo: number; gross_kobo: number; payer_covers_fee: boolean }
interface ChargeResult { reference: string; status: 'started' | 'success' | 'failed'; message: string; net_kobo: number; gross_kobo: number; card: SavedCard | null; available_kobo: number }

export const cardLabel = (c: SavedCard) => `${c.brand ? c.brand[0]!.toUpperCase() + c.brand.slice(1) : 'Card'} ••${c.last4}`;

/** The "Pay with card" panel on Add money. */
export function CardPanel({ suggested }: { suggested: number }) {
  const { reload, koboSay, openSheet, closeSheet, toast } = useStore();
  const [amount, setAmount] = useState(Math.max(suggested, 0) || 2_000_000);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [cards, setCards] = useState<SavedCard[]>([]);
  const [save, setSave] = useState(true);
  const { busy, error, setError, run } = useAction();

  useEffect(() => { api.get<SavedCard[]>('/cards').then(setCards).catch(() => {}); }, []);
  useEffect(() => {
    setError('');
    const t = window.setTimeout(() => api.get<Quote>(`/funding/card/quote?amount_kobo=${amount}`).then(setQuote).catch((e) => { setQuote(null); setError(e.message); }), 200);
    return () => window.clearTimeout(t);
  }, [amount]); // eslint-disable-line react-hooks/exhaustive-deps

  const payNew = () => run(async () => {
    const r = await api.post<{ authorization_url: string }>('/funding/card/start', { amount_kobo: amount, save_card: save });
    window.location.href = r.authorization_url; // Paystack's secure page; it sends you back to /fund/card
  });
  const payWith = (card: SavedCard) => openSheet(
    <ConfirmCharge card={card} quote={quote!} onConfirm={() => run(async () => {
      closeSheet();
      const r = await api.post<ChargeResult>('/funding/card/charge', { card_id: card.id, amount_kobo: amount });
      await reload();
      if (r.status === 'success') koboSay('fill', `${N(r.net_kobo)} added from ${cardLabel(card)}.`);
      else if (r.status === 'failed') { setError(r.message || "The card was declined."); koboSay('puddle', "That card didn't go through."); }
      else toast('Still confirming with your bank. We\'ll tell you when it lands.');
    })} />,
  );

  if (quote && !quote.available) return <div className="card small muted">Card payments aren't set up yet. Use a bank transfer for now.</div>;
  const quick = [...new Set([suggested, 2_000_000, 5_000_000, 10_000_000].filter((x) => x >= 10_000))].slice(0, 4);
  return (
    <div className="card stack" style={{ gap: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <b>Pay with card</b>{quote?.test_mode && <span className="pill p-wait">Test mode</span>}
      </div>
      <div className="quick">{quick.map((q) => <button key={q} aria-pressed={amount === q} onClick={() => setAmount(q)}>{N(q)}</button>)}</div>
      <div className="field"><label htmlFor="card-amt">Amount to add (₦)</label>
        <input id="card-amt" inputMode="numeric" value={Math.round(amount / 100) || ''} onChange={(e) => setAmount(Number(e.target.value.replace(/\D/g, '')) * 100)} /></div>
      {quote && (
        <div className="small" style={{ display: 'grid', gap: 4 }}>
          <div className="kv"><span className="muted">Added to your balance</span><b className="num">{N(quote.net_kobo)}</b></div>
          <div className="kv"><span className="muted">Card fee (Paystack)</span><b className="num">{quote.payer_covers_fee ? N(quote.fee_kobo) : 'On us'}</b></div>
          <div className="kv"><span className="muted">Charged to your card</span><b className="num">{N(quote.gross_kobo)}</b></div>
        </div>
      )}
      {error && <div className="error-card">{error}</div>}
      {cards.map((c) => (
        <button key={c.id} className="btn btn-primary btn-block" disabled={busy || !quote} onClick={() => payWith(c)}>
          Top up with {cardLabel(c)}
        </button>
      ))}
      <button className={`btn ${cards.length ? 'btn-soft' : 'btn-primary'} btn-block`} disabled={busy || !quote} onClick={payNew}>
        {cards.length ? 'Use a different card' : 'Pay with card'}
      </button>
      <label className="small" style={{ display: 'flex', gap: 8, alignItems: 'center', cursor: 'pointer' }}>
        <input type="checkbox" checked={save} onChange={(e) => setSave(e.target.checked)} /> Save this card for one-tap top-ups
      </label>
      <p className="small muted" style={{ margin: 0 }}>🔒 You'll pay on Paystack's secure page. SpenDrip never sees your card number.{quote?.test_mode ? ' Test mode: no real card is charged.' : ''}</p>
    </div>
  );
}

function ConfirmCharge({ card, quote, onConfirm }: { card: SavedCard; quote: Quote; onConfirm: () => void }) {
  const { closeSheet } = useStore();
  return (
    <>
      <h3>Top up {N(quote.net_kobo)}?</h3>
      <p className="muted" style={{ marginTop: -6 }}>We'll charge {N(quote.gross_kobo)} to {cardLabel(card)}{quote.payer_covers_fee && quote.fee_kobo ? `, including the ${N(quote.fee_kobo)} card fee` : ''}.</p>
      <div style={{ display: 'flex', gap: 8 }}>
        <button className="btn btn-soft" style={{ flex: 1 }} onClick={closeSheet}>Cancel</button>
        <button className="btn btn-primary" style={{ flex: 1 }} onClick={onConfirm}>Top up</button>
      </div>
    </>
  );
}

/** Paystack sends people back here with ?reference=… after paying. */
export default function CardReturn() {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const { reload, confetti } = useStore();
  const ref = params.get('reference') ?? params.get('trxref') ?? '';
  const [result, setResult] = useState<ChargeResult | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let tries = 0, stop = false;
    const check = async () => {
      try {
        const r = await api.post<ChargeResult>('/funding/card/verify', { reference: ref });
        if (stop) return;
        if (r.status === 'started' && tries++ < 6) { window.setTimeout(check, 2500); return; } // the bank is still confirming
        setResult(r);
        if (r.status === 'success') { reload(); confetti(); }
      } catch (e: any) { if (!stop) setError(e.message); }
    };
    if (ref) check(); else setError("We couldn't find that payment.");
    return () => { stop = true; };
  }, [ref]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="stack" style={{ alignItems: 'center', textAlign: 'center', maxWidth: 460, margin: '0 auto', paddingTop: 20 }}>
      {!result && !error && <><Kobo mood="waiting" size={96} /><Spinner label="Confirming your payment…" /></>}
      {result?.status === 'success' && (
        <>
          <Kobo mood="celebrate" size={110} />
          <h1 className="h1" style={{ margin: 0 }}>{N(result.net_kobo)} added 🎉</h1>
          <p className="muted" style={{ margin: 0 }}>Your balance is now {N(result.available_kobo)}.{result.card ? ` ${cardLabel(result.card)} is saved for one-tap top-ups.` : ''}</p>
        </>
      )}
      {result?.status === 'failed' && (
        <><Kobo mood="puddle" size={96} /><h1 className="h1" style={{ margin: 0 }}>That didn't go through</h1><p className="muted" style={{ margin: 0 }}>{result.message || 'Your card was not charged.'}</p></>
      )}
      {result?.status === 'started' && (
        <><Kobo mood="waiting" size={96} /><h1 className="h1" style={{ margin: 0 }}>Still confirming</h1><p className="muted" style={{ margin: 0 }}>Your bank hasn't confirmed yet. We'll add the money as soon as it does.</p></>
      )}
      {error && <><Kobo mood="puddle" size={96} /><div className="error-card">{error}</div></>}
      <div style={{ display: 'flex', gap: 8, width: '100%' }}>
        <button className="btn btn-soft" style={{ flex: 1 }} onClick={() => nav('/fund')}>Add money</button>
        <button className="btn btn-primary" style={{ flex: 1 }} onClick={() => nav('/')}>Go to Home</button>
      </div>
    </div>
  );
}
