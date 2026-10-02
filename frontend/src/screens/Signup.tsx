import { useEffect, useRef, useState } from 'react';
import { api } from '../lib/api';
import { createPasskey, passkeysSupported } from '../lib/passkey';
import { useStore } from '../lib/store';
import type { Me } from '../lib/types';
import { Icon, PinDots, PinPad, Spinner, Wordmark, useAction } from '../components/ui';
import Kobo from '../components/Kobo';

/** Sign-up: email → code → name → PIN → Face ID. Identity checks come later, from inside the app (see Verify). */
type Step = 'email' | 'code' | 'name' | 'pin' | 'face' | 'done';
const ACCOUNT: Step[] = ['email', 'code', 'name'];
const SEC: Step[] = ['pin', 'face'];
const WEAK = new Set(['0000', '1111', '1234', '4321', '1212', '2222', '9999']);
export const looksLikeEmail = (v: string) => /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v.trim());

function startStep(me: Me | null): Step {
  if (me?.signed_in && me.user && !me.user.has_name) return 'name';
  if (me?.signed_in && !me.user?.has_pin) return 'pin';
  return me?.signup?.step === 'code' ? 'code' : 'email';
}

export default function Signup({ onExit, onFinished }: { onExit: () => void; onFinished: (goTo: 'home' | 'new' | 'verify') => void }) {
  const { me, setMe, refreshMe, confetti, toast } = useStore();
  const [step, setStep] = useState<Step>(() => startStep(me));
  const [emailMasked, setEmailMasked] = useState(me?.signup?.email_masked ?? '');
  const [devCode, setDevCode] = useState('');

  const back = () => (step === 'code' ? setStep('email') : onExit());
  const header = (canBack: boolean) => (
    <>
      <div className="kyc-top">
        {canBack ? <button className="icon-btn" aria-label="Back" onClick={back}>{Icon.back}</button> : <Wordmark />}
        <span className="small muted" style={{ fontWeight: 700 }}>
          {ACCOUNT.includes(step) ? `Step ${ACCOUNT.indexOf(step) + 1} of 3` : SEC.includes(step) ? 'Secure your account' : ''}
        </span>
      </div>
      {ACCOUNT.includes(step) && <div className="kyc-prog">{ACCOUNT.map((s, i) => <i key={s} className={i <= ACCOUNT.indexOf(step) ? 'on' : ''} />)}</div>}
      {SEC.includes(step) && <div className="kyc-prog">{SEC.map((s, i) => <i key={s} className={i <= SEC.indexOf(step) ? 'on' : ''} />)}</div>}
    </>
  );

  return (
    <div className="kyc">
      <div className="kyc-inner" key={step}>
        {step === 'email' && <EmailStep header={header(true)} onNext={(masked, code) => { setEmailMasked(masked); setDevCode(code ?? ''); setStep('code'); }} />}
        {step === 'code' && <OtpStep header={header(true)} emailMasked={emailMasked} devCode={devCode} setDevCode={setDevCode}
          onNext={(m) => { setMe(m); setStep(m.user?.has_name ? 'pin' : 'name'); }} />}
        {step === 'name' && <NameStep header={header(false)} onNext={(m) => { setMe(m); setStep('pin'); }} />}
        {step === 'pin' && <PinStep header={header(false)} onNext={(m) => { setMe(m); setStep(passkeysSupported() ? 'face' : 'done'); if (!passkeysSupported()) confetti(); }} />}
        {step === 'face' && <FaceStep header={header(false)} onNext={async (on) => { await refreshMe(); if (on) toast('Face ID is on'); setStep('done'); confetti(); }} />}
        {step === 'done' && <DoneStep header={header(false)} onGo={onFinished} />}
      </div>
    </div>
  );
}

/* ---------------- step 1: email ---------------- */
function EmailStep({ header, onNext }: { header: React.ReactNode; onNext: (masked: string, devCode?: string) => void }) {
  const [email, setEmail] = useState('');
  const { busy, error, setError, run } = useAction();
  const ok = looksLikeEmail(email);
  const start = () => ok && run(async () => {
    try { const r = await api.post<any>('/signup/start', { email }); onNext(r.email_masked, r.dev_code); }
    catch (e: any) { if (e.code === 'otp_wait') { onNext(email.trim().toLowerCase()); return; } throw e; }
  });
  return (
    <>
      {header}
      <h2>What's your email?</h2>
      <p className="lead">We'll send you a 6-digit code to confirm it. You'll use this email to sign in.</p>
      <div className="field"><label htmlFor="em">Email</label>
        <input id="em" type="email" inputMode="email" autoComplete="email" autoCapitalize="none" placeholder="you@example.com" value={email} autoFocus
          onChange={(e) => { setEmail(e.target.value); setError(''); }} onKeyDown={(e) => e.key === 'Enter' && start()} /></div>
      {busy && <Spinner label="Sending your code…" />}
      {error && <div className="error-card">{error}</div>}
      <div className="kyc-actions">
        <button className="btn btn-primary btn-block" style={{ height: 56 }} disabled={!ok || busy} onClick={start}>Email me a code</button>
        <div className="lockline"><span>🔒</span><span>No spam. We only email you about your account and your drips.</span></div>
      </div>
    </>
  );
}

/* ---------------- step 3: name ---------------- */
function NameStep({ header, onNext }: { header: React.ReactNode; onNext: (me: Me) => void }) {
  const [first, setFirst] = useState('');
  const [last, setLast] = useState('');
  const { busy, error, run } = useAction();
  const save = () => first.trim() && run(async () => onNext(await api.post<Me>('/signup/name', { first_name: first, last_name: last })));
  return (
    <>
      {header}
      <h2>What should we call you?</h2>
      <p className="lead">This is how you'll appear in the app and in messages to the people you pay.</p>
      <div className="field"><label htmlFor="fn">First name</label>
        <input id="fn" autoComplete="given-name" placeholder="Adaeze" value={first} autoFocus onChange={(e) => setFirst(e.target.value)} /></div>
      <div className="field"><label htmlFor="ln">Last name</label>
        <input id="ln" autoComplete="family-name" placeholder="Okonkwo" value={last} onChange={(e) => setLast(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && save()} /></div>
      {error && <div className="error-card">{error}</div>}
      <div className="kyc-actions"><button className="btn btn-primary btn-block" style={{ height: 56 }} disabled={!first.trim() || busy} onClick={save}>Continue</button></div>
    </>
  );
}

/* ---------------- step 2: email code ---------------- */
export function OtpBoxes({ value, onChange, ok }: { value: string; onChange: (v: string) => void; ok?: boolean }) {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => { ref.current?.focus({ preventScroll: true }); }, []);
  return (
    <label className="otp" aria-label="6-digit code">
      {[0, 1, 2, 3, 4, 5].map((i) => <span key={i} className={ok ? 'ok' : i === value.length ? 'cur' : ''}>{value[i] ?? ''}</span>)}
      <input ref={ref} inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={value} readOnly={ok}
        onChange={(e) => onChange(e.target.value.replace(/\D/g, '').slice(0, 6))} />
    </label>
  );
}

export function useResend(seconds = 30) {
  const [left, setLeft] = useState(seconds);
  useEffect(() => { if (left <= 0) return; const t = window.setTimeout(() => setLeft(left - 1), 1000); return () => window.clearTimeout(t); }, [left]);
  return { left, restart: (n: number = seconds) => setLeft(n) };
}

function OtpStep({ header, emailMasked, devCode, setDevCode, onNext }: {
  header: React.ReactNode; emailMasked: string; devCode: string; setDevCode: (c: string) => void; onNext: (me: Me) => void;
}) {
  const [code, setCode] = useState('');
  const [ok, setOk] = useState(false);
  const { busy, error, setError, run } = useAction();
  const resend = useResend();
  const change = (v: string) => {
    setCode(v); setError('');
    if (v.length === 6) run(async () => {
      try { const m = await api.post<Me>('/signup/otp/verify', { code: v }); setOk(true); window.setTimeout(() => onNext(m), 400); }
      catch (e) { setCode(''); throw e; }
    });
  };
  return (
    <>
      {header}
      <h2>Check your email</h2>
      <p className="lead">We sent a 6-digit code to <b style={{ color: 'var(--ink)' }}>{emailMasked || 'your email'}</b>. It can take a minute, and sometimes lands in spam.</p>
      <OtpBoxes value={code} onChange={change} ok={ok} />
      {busy ? <Spinner label="Checking code…" /> : <p className="err">{error}</p>}
      <p className="small muted" style={{ textAlign: 'center', margin: 0 }}>
        {resend.left > 0 ? `Resend code in 0:${String(resend.left).padStart(2, '0')}` : (
          <button className="link" onClick={() => run(async () => { const r = await api.post<any>('/signup/otp/resend'); setDevCode(r.dev_code ?? ''); resend.restart(); })}>Resend code</button>
        )}
      </p>
      {devCode && <div className="kyc-actions"><p className="dev-note">Test mode: your code is <b>{devCode}</b>.</p></div>}
    </>
  );
}

/* ---------------- PIN ---------------- */
function PinStep({ header, onNext }: { header: React.ReactNode; onNext: (me: Me) => void }) {
  const [first, setFirst] = useState<string | null>(null);
  const [pin, setPin] = useState('');
  const [bad, setBad] = useState(false);
  const { error, setError, run } = useAction();
  const change = (v: string) => {
    setPin(v); setError(''); setBad(false);
    if (v.length < 4) return;
    window.setTimeout(() => {
      if (!first) {
        if (WEAK.has(v)) { setError('That PIN is too easy to guess. Pick another.'); setBad(true); setPin(''); return; }
        setFirst(v); setPin(''); return;
      }
      if (v !== first) { setError("PINs don't match. Let's start again."); setBad(true); setFirst(null); setPin(''); return; }
      run(async () => onNext(await api.post<Me>('/auth/pin', { pin: v }))).then(() => setPin(''));
    }, 180);
  };
  return (
    <>
      {header}
      <h2 style={{ textAlign: 'center' }}>{first ? 'Enter your PIN again' : 'Create a 4-digit PIN'}</h2>
      <p className="lead" style={{ textAlign: 'center' }}>{first ? 'Just to be sure.' : "You'll use it to open SpenDrip and approve changes to your plans."}</p>
      <PinDots n={pin.length} bad={bad} />
      <p className="err">{error}</p>
      <PinPad value={pin} onChange={change} />
      {!first && <p className="small muted" style={{ textAlign: 'center', margin: 0 }}>Avoid 1234, 0000 or your birth year.</p>}
    </>
  );
}

/* ---------------- Face ID ---------------- */
function FaceStep({ header, onNext }: { header: React.ReactNode; onNext: (on: boolean) => void }) {
  const [scanning, setScanning] = useState(false);
  const { error, run } = useAction();
  const turnOn = () => run(async () => {
    setScanning(true);
    try {
      const opts = await api.post<any>('/auth/passkey/register/options');
      const credential = await createPasskey(opts);
      await api.post('/auth/passkey/register/verify', { credential, device_label: navigator.platform || 'This device' });
      onNext(true);
    } catch (e: any) {
      if (e?.name === 'NotAllowedError') throw new Error("Face ID wasn't turned on. You can try again, or do it later in Profile.");
      throw e;
    } finally { setScanning(false); }
  });
  return (
    <>
      {header}
      <div className={`face-ic ${scanning ? 'scan' : ''}`}>{Icon.face}</div>
      <h2 style={{ textAlign: 'center' }}>Open SpenDrip with Face ID</h2>
      <p className="lead" style={{ textAlign: 'center' }}>Quicker than typing your PIN. You can still use your PIN whenever you want.</p>
      {error && <div className="error-card">{error}</div>}
      <div className="kyc-actions">
        <button className="btn btn-primary btn-block" style={{ height: 56 }} onClick={turnOn} disabled={scanning}>Turn on Face ID</button>
        <button className="btn btn-soft btn-block" onClick={() => onNext(false)}>Not now</button>
      </div>
    </>
  );
}

/* ---------------- done ---------------- */
function DoneStep({ header, onGo }: { header: React.ReactNode; onGo: (to: 'home' | 'new' | 'verify') => void }) {
  const { me } = useStore();
  return (
    <>
      {header}
      <div style={{ display: 'grid', placeItems: 'center', marginTop: 34 }}><Kobo mood="celebrate" size={110} /></div>
      <h2 style={{ textAlign: 'center' }}>You're in, {me?.user?.first_name ?? 'friend'} 🎉</h2>
      <p className="lead" style={{ textAlign: 'center' }}>Set up your plans now. When you're ready to add money, verify your identity. It takes about two minutes.</p>
      <div className="kyc-actions">
        <button className="btn btn-primary btn-block" style={{ height: 56 }} onClick={() => onGo('new')}>Create my first plan</button>
        <button className="btn btn-soft btn-block" onClick={() => onGo('verify')}>Verify my identity now</button>
        <button className="link small" style={{ alignSelf: 'center' }} onClick={() => onGo('home')}>Go to Home</button>
      </div>
    </>
  );
}
