import { useEffect, useRef, useState } from 'react';
import { api } from '../lib/api';
import { createPasskey, passkeysSupported } from '../lib/passkey';
import { useStore } from '../lib/store';
import type { Me } from '../lib/types';
import { Icon, PinDots, PinPad, Spinner, Wordmark, useAction } from '../components/ui';
import Kobo from '../components/Kobo';

type Step = 'nin' | 'document' | 'selfie' | 'otp' | 'pin' | 'face' | 'done';
const KYC: Step[] = ['nin', 'document', 'selfie'];
const SEC: Step[] = ['otp', 'pin', 'face'];
const ID_TYPES = [['nin', 'NIN slip / ID card'], ['dl', "Driver's licence"], ['vc', "Voter's card"], ['pp', 'Passport']] as const;
const WEAK = new Set(['0000', '1111', '1234', '4321', '1212', '2222', '9999']);
const fmtNin = (v: string) => v.replace(/\D/g, '').slice(0, 11).replace(/^(\d{3})(\d{0,4})(\d{0,4}).*/, (_, a, b, c) => [a, b, c].filter(Boolean).join(' '));

function startStep(me: Me | null): Step {
  if (me?.signed_in && !me.user?.has_pin) return 'pin';
  const s = me?.signup?.step;
  return s === 'document' ? 'document' : s === 'selfie' ? 'selfie' : s === 'otp' ? 'otp' : 'nin';
}

export default function Signup({ onExit, onFinished }: { onExit: () => void; onFinished: (goTo: 'home' | 'new') => void }) {
  const { me, setMe, refreshMe, confetti, toast } = useStore();
  const [step, setStep] = useState<Step>(() => startStep(me));
  const [phoneMasked, setPhoneMasked] = useState(me?.signup?.phone_masked ?? '');
  const [devCode, setDevCode] = useState('');
  const dev = !!me?.dev_tools;

  const back = () => {
    const order: Step[] = ['nin', 'document', 'selfie'];
    const i = order.indexOf(step);
    if (i > 0) setStep(order[i - 1]!); else onExit();
  };
  const header = (canBack: boolean) => (
    <>
      <div className="kyc-top">
        {canBack ? <button className="icon-btn" aria-label="Back" onClick={back}>{Icon.back}</button> : <Wordmark />}
        <span className="small muted" style={{ fontWeight: 700 }}>
          {KYC.includes(step) ? `Step ${KYC.indexOf(step) + 1} of 3` : SEC.includes(step) ? 'Secure your account' : ''}
        </span>
      </div>
      {KYC.includes(step) && <div className="kyc-prog">{KYC.map((s, i) => <i key={s} className={i <= KYC.indexOf(step) ? 'on' : ''} />)}</div>}
      {SEC.includes(step) && <div className="kyc-prog">{SEC.map((s, i) => <i key={s} className={i <= SEC.indexOf(step) ? 'on' : ''} />)}</div>}
    </>
  );

  return (
    <div className="kyc">
      <div className="kyc-inner" key={step}>
        {step === 'nin' && <NinStep header={header(true)} onNext={() => setStep('document')} />}
        {step === 'document' && <DocStep header={header(true)} dev={dev} onNext={() => setStep('selfie')} />}
        {step === 'selfie' && <SelfieStep header={header(true)} dev={dev} onNext={(masked, code) => { setPhoneMasked(masked); setDevCode(code ?? ''); setStep('otp'); }} />}
        {step === 'otp' && <OtpStep header={header(false)} phoneMasked={phoneMasked} devCode={devCode} setDevCode={setDevCode}
          onNext={(m) => { setMe(m); setStep('pin'); }} />}
        {step === 'pin' && <PinStep header={header(false)} onNext={(m) => { setMe(m); setStep(passkeysSupported() ? 'face' : 'done'); if (!passkeysSupported()) confetti(); }} />}
        {step === 'face' && <FaceStep header={header(false)} onNext={async (on) => { await refreshMe(); if (on) toast('Face ID is on'); setStep('done'); confetti(); }} />}
        {step === 'done' && <DoneStep header={header(false)} onGo={onFinished} />}
      </div>
    </div>
  );
}

/* ---------------- step 1: NIN ---------------- */
function NinStep({ header, onNext }: { header: React.ReactNode; onNext: () => void }) {
  const [nin, setNin] = useState('');
  const [found, setFound] = useState<{ name: string; date_of_birth: string; phone_masked: string } | null>(null);
  const { busy, error, setError, run } = useAction();
  const digits = nin.replace(/\D/g, '');
  const check = () => run(async () => setFound(await api.post('/signup/nin', { nin: digits })));
  const confirm = () => run(async () => { await api.post('/signup/confirm'); onNext(); });
  const initials = found?.name.split(' ').map((w) => w[0]).join('').slice(0, 2);
  const dob = found ? new Date(found.date_of_birth).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '';
  return (
    <>
      {header}
      <h2>What's your NIN?</h2>
      <p className="lead">Your 11-digit National Identification Number. We use it to check it's really you.</p>
      <input className="nin-input" inputMode="numeric" autoComplete="off" placeholder="000 0000 0000" aria-label="NIN" autoFocus
        value={fmtNin(nin)} readOnly={!!found} onChange={(e) => { setNin(e.target.value); setError(''); }}
        onKeyDown={(e) => { if (e.key === 'Enter' && digits.length === 11 && !found) check(); }} />
      {!found && !busy && <p className="small muted" style={{ margin: '-6px 0 0', textAlign: 'center' }}>Don't know it? Dial <b>*346#</b> from the phone number linked to your NIN.</p>}
      {busy && !found && <Spinner label="Checking your NIN…" />}
      {error && <div className="error-card">{error}</div>}
      {found && (
        <div className="found">
          <div className="who"><span className="av">{initials}</span>
            <div><div className="eyebrow" style={{ color: 'var(--mint)' }}>We found you</div><b style={{ fontSize: 17 }}>{found.name}</b>
              <div className="small muted">Born {dob} · Phone {found.phone_masked}</div></div></div>
          <b>Is this you?</b>
        </div>
      )}
      <div className="kyc-actions">
        {found ? (
          <>
            <button className="btn btn-primary btn-block" style={{ height: 56 }} disabled={busy} onClick={confirm}>Yes, that's me</button>
            <button className="btn btn-soft btn-block" onClick={() => { setFound(null); setNin(''); }}>No, let me re-enter it</button>
          </>
        ) : (
          <button className="btn btn-primary btn-block" style={{ height: 56 }} disabled={digits.length !== 11 || busy} onClick={check}>Check my NIN</button>
        )}
        <div className="lockline"><span>🔒</span><span>Your NIN is encrypted. We only use it to verify you, and the people you send money to never see it.</span></div>
      </div>
    </>
  );
}

/* ---------------- photos ---------------- */
function sampleBlob(kind: 'id' | 'selfie'): Promise<Blob> {
  const c = document.createElement('canvas');
  const x = c.getContext('2d')!;
  if (kind === 'id') {
    c.width = 640; c.height = 404;
    x.fillStyle = '#E8F3EC'; x.fillRect(0, 0, 640, 404); x.fillStyle = '#0E7A4B'; x.fillRect(0, 0, 640, 70);
    x.fillStyle = '#fff'; x.font = 'bold 26px sans-serif'; x.fillText('NATIONAL IDENTITY CARD (SAMPLE)', 26, 45);
    x.fillStyle = '#C9D9CF'; x.fillRect(30, 100, 170, 210);
    x.fillStyle = '#33473C'; x.font = 'bold 22px sans-serif'; x.fillText('OKONKWO ADAEZE', 230, 150); x.fillText('14 MAR 1994', 230, 210);
  } else {
    c.width = c.height = 400;
    x.fillStyle = '#FFD9A0'; x.fillRect(0, 0, 400, 400); x.fillStyle = '#7A4A2A';
    x.beginPath(); x.arc(200, 170, 92, 0, Math.PI * 2); x.fill(); x.beginPath(); x.ellipse(200, 420, 150, 120, 0, 0, Math.PI * 2); x.fill();
  }
  return new Promise((r) => c.toBlob((b) => r(b!), 'image/jpeg', 0.85));
}

function useUpload(path: string, extra: Record<string, string> = {}) {
  const [preview, setPreview] = useState('');
  const [blob, setBlob] = useState<Blob | null>(null);
  const take = (b: Blob) => { setBlob(b); setPreview(URL.createObjectURL(b)); };
  const send = async () => {
    const fd = new FormData();
    fd.append('image', blob!, 'photo.jpg');
    Object.entries(extra).forEach(([k, v]) => fd.append(k, v));
    return api.post<any>(path, fd);
  };
  return { preview, blob, take, send, reset: () => { setBlob(null); setPreview(''); } };
}

const FileButton = ({ label, capture, onPick, primary }: { label: string; capture?: 'user' | 'environment'; onPick: (b: Blob) => void; primary?: boolean }) => (
  <label className={`btn ${primary ? 'btn-primary' : 'btn-soft'} btn-block file-btn`} style={primary ? { height: 56 } : undefined}>
    {label}<input type="file" accept="image/*" capture={capture} onChange={(e) => { const f = e.target.files?.[0]; if (f) onPick(f); e.target.value = ''; }} />
  </label>
);

/* ---------------- step 2: ID ---------------- */
function DocStep({ header, dev, onNext }: { header: React.ReactNode; dev: boolean; onNext: () => void }) {
  const [idType, setIdType] = useState('nin');
  const up = useUpload('/signup/document', { id_type: idType });
  const { busy, error, run } = useAction();
  return (
    <>
      {header}
      <h2>Snap your ID</h2>
      <p className="lead">A clear photo of the front. Lay it flat in good light, with all four corners in view.</p>
      <div className="id-types" role="group" aria-label="ID type">
        {ID_TYPES.map(([k, l]) => <button key={k} aria-pressed={idType === k} onClick={() => setIdType(k)}>{l}</button>)}
      </div>
      <div className={`id-frame ${up.preview ? 'has' : ''}`}>
        {up.preview ? <img src={up.preview} alt="Your ID" /> : (
          <><div className="ghost"><i className="ph" /><span className="ln"><i style={{ width: '80%' }} /><i /><i style={{ width: '60%' }} /><i style={{ width: '70%' }} /></span></div>
            <span className="corner tl" /><span className="corner tr" /><span className="corner bl" /><span className="corner br" /></>
        )}
      </div>
      {busy && <Spinner label="Checking your ID…" />}
      {error && <div className="error-card">{error}</div>}
      <div className="kyc-actions">
        {up.preview ? (
          <>
            <button className="btn btn-primary btn-block" style={{ height: 56 }} disabled={busy} onClick={() => run(async () => { await up.send(); onNext(); })}>Use this photo</button>
            <FileButton label="Retake" capture="environment" onPick={up.take} />
          </>
        ) : (
          <>
            <FileButton primary label="📷 Take a photo" capture="environment" onPick={up.take} />
            <FileButton label="Upload from gallery" onPick={up.take} />
            {dev && <button className="demo-link" onClick={async () => up.take(await sampleBlob('id'))}>Use a sample ID (demo)</button>}
          </>
        )}
      </div>
    </>
  );
}

/* ---------------- step 3: selfie ---------------- */
function SelfieStep({ header, dev, onNext }: { header: React.ReactNode; dev: boolean; onNext: (phoneMasked: string, devCode?: string) => void }) {
  const up = useUpload('/signup/selfie');
  const { busy, error, run } = useAction();
  const submit = () => run(async () => { const r = await up.send(); onNext(r.phone_masked, r.dev_code); });
  return (
    <>
      {header}
      <h2>Now a quick selfie</h2>
      <p className="lead">We match your face to your ID. It takes a second.</p>
      <div className={`selfie-frame ${up.preview ? 'has' : ''}`}>{up.preview ? <img src={up.preview} alt="Your selfie" /> : Icon.person}</div>
      {busy ? <Spinner label="Matching your face to your ID…" /> : !up.preview && (
        <div className="tips"><span>💡 Good light</span><span>🧢 No cap or shades</span><span>🙂 Look straight</span></div>
      )}
      {error && <div className="error-card">{error}</div>}
      <div className="kyc-actions">
        {up.preview ? (
          <>
            <button className="btn btn-primary btn-block" style={{ height: 56 }} disabled={busy} onClick={submit}>Use this selfie</button>
            <FileButton label="Retake" capture="user" onPick={up.take} />
          </>
        ) : (
          <>
            <FileButton primary label="🤳 Take selfie" capture="user" onPick={up.take} />
            {dev && <button className="demo-link" onClick={async () => up.take(await sampleBlob('selfie'))}>Use a sample selfie (demo)</button>}
          </>
        )}
      </div>
    </>
  );
}

/* ---------------- SMS code ---------------- */
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
  return { left, restart: () => setLeft(seconds) };
}

function OtpStep({ header, phoneMasked, devCode, setDevCode, onNext }: {
  header: React.ReactNode; phoneMasked: string; devCode: string; setDevCode: (c: string) => void; onNext: (me: Me) => void;
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
      <h2>Enter the code we texted you</h2>
      <p className="lead">We sent a 6-digit code to <b style={{ color: 'var(--ink)' }}>{phoneMasked || 'your phone'}</b>, the number on your NIN record.</p>
      <OtpBoxes value={code} onChange={change} ok={ok} />
      {busy ? <Spinner label="Checking code…" /> : <p className="err">{error}</p>}
      <p className="small muted" style={{ textAlign: 'center', margin: 0 }}>
        {resend.left > 0 ? `Resend code in 0:${String(resend.left).padStart(2, '0')}` : (
          <button className="link" onClick={() => run(async () => { const r = await api.post<any>('/signup/otp/resend'); setDevCode(r.dev_code ?? ''); resend.restart(); })}>Resend code</button>
        )}
      </p>
      {devCode && <div className="kyc-actions"><p className="dev-note">Test mode: SMS isn't connected yet. Your code is <b>{devCode}</b>.</p></div>}
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
function DoneStep({ header, onGo }: { header: React.ReactNode; onGo: (to: 'home' | 'new') => void }) {
  const { me } = useStore();
  const fa = me?.user?.funding_account;
  return (
    <>
      {header}
      <div style={{ display: 'grid', placeItems: 'center', marginTop: 34 }}><Kobo mood="celebrate" size={110} /></div>
      <h2 style={{ textAlign: 'center' }}>You're verified, {me?.user?.first_name ?? 'friend'} 🎉</h2>
      <p className="lead" style={{ textAlign: 'center' }}>Your SpenDrip account is ready. Send money to it any time to fund your plans.</p>
      {fa && <div className="acct"><span className="small muted" style={{ fontWeight: 700 }}>Your SpenDrip account</span>
        <span className="acct-no num">{fa.account_number.replace(/(\d{4})(\d{3})(\d{3})/, '$1 $2 $3')}</span>
        <span style={{ fontWeight: 700 }}>{fa.bank_name} · {fa.account_name}</span></div>}
      <div className="kyc-actions">
        <button className="btn btn-primary btn-block" style={{ height: 56 }} onClick={() => onGo('new')}>Create my first plan</button>
        <button className="btn btn-soft btn-block" onClick={() => onGo('home')}>Go to Home</button>
      </div>
    </>
  );
}
