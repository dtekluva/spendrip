import { useState } from 'react';
import { api } from '../lib/api';
import { useStore } from '../lib/store';
import type { Me } from '../lib/types';
import { Icon, PinDots, PinPad, Spinner, Wordmark, useAction } from '../components/ui';
import { OtpBoxes, useResend } from './Signup';

/** Signing in on a new device, or after "Forgot PIN": phone → SMS code → PIN (or a new PIN). */
export default function SignIn({ forgot: startForgot = false, onBack, onDone }: { forgot?: boolean; onBack: () => void; onDone: (m: Me) => void }) {
  const { me } = useStore();
  const [step, setStep] = useState<'phone' | 'code' | 'pin'>('phone');
  const [phone, setPhone] = useState('');
  const [masked, setMasked] = useState('');
  const [devCode, setDevCode] = useState('');
  const [code, setCode] = useState('');
  const [forgot, setForgot] = useState(startForgot);
  const [pin, setPin] = useState('');
  const [first, setFirst] = useState<string | null>(null);
  const { busy, error, setError, run } = useAction();
  const resend = useResend();

  const [note, setNote] = useState('');
  const start = () => run(async () => {
    try {
      const r = await api.post<any>('/auth/signin/start', { phone });
      setMasked(r.phone_masked); setDevCode(r.dev_code ?? ''); setNote(''); if (r.pin_locked) setForgot(true); setStep('code'); resend.restart();
    } catch (e: any) {
      if (e.code !== 'otp_wait') throw e;
      // A code went out moments ago and is still valid: go to the code screen instead of blocking.
      const digits = phone.replace(/\D/g, '').replace(/^234/, '0');
      setMasked(`${digits.slice(0, 4)} ••• ${digits.slice(-4)}`);
      setNote('We sent you a code a moment ago. Use that one, or wait to get a new one.');
      setStep('code'); resend.restart(Number(e.message.match(/\d+/)?.[0] ?? 30));
    }
  });
  const finish = (p: string) => run(async () => {
    try { onDone(await api.post<Me>('/auth/signin/verify', forgot ? { phone, code, new_pin: p } : { phone, code, pin: p })); }
    catch (e: any) { setPin(''); setFirst(null); if (e.code?.startsWith('otp')) { setCode(''); setStep('code'); } throw e; }
  });
  const pinChange = (v: string) => {
    setPin(v); setError('');
    if (v.length < 4) return;
    window.setTimeout(() => {
      if (!forgot) return finish(v);
      if (!first) { setFirst(v); setPin(''); return; }
      if (v !== first) { setError("PINs don't match. Let's start again."); setFirst(null); setPin(''); return; }
      finish(v);
    }, 180);
  };

  return (
    <div className="kyc">
      <div className="kyc-inner" key={step}>
        <div className="kyc-top">
          <button className="icon-btn" aria-label="Back" onClick={() => (step === 'phone' ? onBack() : setStep(step === 'pin' ? 'code' : 'phone'))}>{Icon.back}</button>
          <span className="small muted" style={{ fontWeight: 700 }}>{forgot ? 'Reset your PIN' : 'Sign in'}</span>
        </div>
        {step === 'phone' && (
          <>
            <Wordmark style={{ fontSize: 26 }} />
            <h2>{forgot ? "Let's reset your PIN" : 'Welcome back'}</h2>
            <p className="lead">Enter the phone number on your NIN record. We'll text you a code.</p>
            <div className="field"><label htmlFor="ph">Phone number</label>
              <input id="ph" inputMode="tel" autoComplete="tel" placeholder="0803 123 4567" value={phone} autoFocus
                onChange={(e) => { setPhone(e.target.value); setError(''); }} onKeyDown={(e) => e.key === 'Enter' && start()} /></div>
            {error && <div className="error-card">{error}</div>}
            <div className="kyc-actions"><button className="btn btn-primary btn-block" style={{ height: 56 }} disabled={busy || phone.replace(/\D/g, '').length < 11} onClick={start}>Text me a code</button></div>
          </>
        )}
        {step === 'code' && (
          <>
            <h2>Enter the code we texted you</h2>
            <p className="lead">We sent a 6-digit code to <b style={{ color: 'var(--ink)' }}>{masked}</b>.</p>
            {note && <p className="small muted" style={{ margin: 0 }}>{note}</p>}
            <OtpBoxes value={code} onChange={(v) => { setCode(v); setError(''); if (v.length === 6) setStep('pin'); }} />
            <p className="err">{error}</p>
            <p className="small muted" style={{ textAlign: 'center', margin: 0 }}>
              {resend.left > 0 ? `Resend code in 0:${String(resend.left).padStart(2, '0')}` : <button className="link" onClick={start}>Resend code</button>}
            </p>
            {devCode && me?.dev_tools && <div className="kyc-actions"><p className="dev-note">Test mode: SMS isn't connected yet. Your code is <b>{devCode}</b>.</p></div>}
          </>
        )}
        {step === 'pin' && (
          <>
            <h2 style={{ textAlign: 'center' }}>{forgot ? (first ? 'Enter the new PIN again' : 'Choose a new PIN') : 'Enter your PIN'}</h2>
            <PinDots n={pin.length} bad={!!error} />
            {busy ? <Spinner label="Signing you in…" /> : <p className="err">{error}</p>}
            <PinPad value={pin} onChange={pinChange} disabled={busy} />
            {!forgot && <button className="link small" style={{ alignSelf: 'center' }} onClick={() => { setForgot(true); setPin(''); setError(''); }}>Forgot PIN?</button>}
          </>
        )}
      </div>
    </div>
  );
}
