import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { useStore } from '../lib/store';
import type { Me } from '../lib/types';
import { Icon, Spinner, useAction } from '../components/ui';
import Kobo from '../components/Kobo';

/** Verify your identity, from inside the app: NIN or BVN → ID photo → selfie. Unlocks adding money and sending it. */
type Step = 'id' | 'document' | 'selfie' | 'done';
const STEPS: Step[] = ['id', 'document', 'selfie'];
const ID_TYPES = [['nin', 'NIN slip / ID card'], ['dl', "Driver's licence"], ['vc', "Voter's card"], ['pp', 'Passport']] as const;
const fmt11 = (v: string) => v.replace(/\D/g, '').slice(0, 11).replace(/^(\d{3})(\d{0,4})(\d{0,4}).*/, (_, a, b, c) => [a, b, c].filter(Boolean).join(' '));

function startStep(me: Me | null): Step {
  const s = me?.user?.kyc_status;
  return s === 'verified' ? 'done' : s === 'nin_verified' ? 'document' : s === 'doc_uploaded' ? 'selfie' : 'id';
}

export default function Verify() {
  const { me, setMe, reload, confetti } = useStore();
  const nav = useNavigate();
  const [step, setStep] = useState<Step>(() => startStep(me));
  const dev = !!me?.dev_tools;
  const i = STEPS.indexOf(step);
  const back = () => (i > 0 && step !== 'document' ? setStep(STEPS[i - 1]!) : nav(-1));
  const header = (
    <>
      <div className="kyc-top">
        {step === 'done' ? <span /> : <button className="icon-btn" aria-label="Back" onClick={back}>{Icon.back}</button>}
        <span className="small muted" style={{ fontWeight: 700 }}>{step === 'done' ? '' : `Verify your identity · ${i + 1} of 3`}</span>
      </div>
      {step !== 'done' && <div className="kyc-prog">{STEPS.map((s, k) => <i key={s} className={k <= i ? 'on' : ''} />)}</div>}
    </>
  );
  return (
    <div className="kyc verify">
      <div className="kyc-inner" key={step}>
        {step === 'id' && <IdStep header={header} onNext={() => setStep('document')} />}
        {step === 'document' && <DocStep header={header} dev={dev} onNext={() => setStep('selfie')} />}
        {step === 'selfie' && <SelfieStep header={header} dev={dev} onNext={async (m) => { setMe(m); await reload(); confetti(); setStep('done'); }} />}
        {step === 'done' && <DoneStep header={header} />}
      </div>
    </div>
  );
}

/* ---------------- step 1: NIN or BVN ---------------- */
function IdStep({ header, onNext }: { header: React.ReactNode; onNext: () => void }) {
  const [kind, setKind] = useState<'nin' | 'bvn'>('nin');
  const [num, setNum] = useState('');
  const [found, setFound] = useState<{ name: string; date_of_birth: string; phone_masked: string } | null>(null);
  const { busy, error, setError, run } = useAction();
  const digits = num.replace(/\D/g, '');
  const label = kind.toUpperCase();
  const check = () => run(async () => setFound(await api.post('/kyc/lookup', { id_type: kind, number: digits })));
  const confirm = () => run(async () => { await api.post('/kyc/confirm'); onNext(); });
  const initials = found?.name.split(' ').map((w) => w[0]).join('').slice(0, 2);
  const dob = found ? new Date(found.date_of_birth).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '';
  return (
    <>
      {header}
      <h2>Your NIN or BVN</h2>
      <p className="lead">Either one works. We use it to confirm it's really you before any money moves.</p>
      <div className="seg" role="group" aria-label="ID number type">
        {(['nin', 'bvn'] as const).map((k) => (
          <button key={k} aria-pressed={kind === k} disabled={!!found} onClick={() => { setKind(k); setError(''); }}>{k === 'nin' ? 'NIN' : 'BVN'}</button>
        ))}
      </div>
      <input className="nin-input" inputMode="numeric" autoComplete="off" placeholder="000 0000 0000" aria-label={label} autoFocus
        value={fmt11(num)} readOnly={!!found} onChange={(e) => { setNum(e.target.value); setError(''); }}
        onKeyDown={(e) => { if (e.key === 'Enter' && digits.length === 11 && !found) check(); }} />
      {!found && !busy && <p className="small muted" style={{ margin: '-6px 0 0', textAlign: 'center' }}>
        {kind === 'nin' ? <>Don't know it? Dial <b>*346#</b> from the phone number linked to your NIN.</> : <>Don't know it? Dial <b>*565*0#</b> from the phone number linked to your bank account.</>}
      </p>}
      {busy && !found && <Spinner label={`Checking your ${label}…`} />}
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
            <button className="btn btn-soft btn-block" onClick={() => { setFound(null); setNum(''); }}>No, let me re-enter it</button>
          </>
        ) : (
          <button className="btn btn-primary btn-block" style={{ height: 56 }} disabled={digits.length !== 11 || busy} onClick={check}>Check my {label}</button>
        )}
        <div className="lockline"><span>🔒</span><span>We only use your {label} to verify you. The people you send money to never see it.</span></div>
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
  const up = useUpload('/kyc/document', { id_type: idType });
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
function SelfieStep({ header, dev, onNext }: { header: React.ReactNode; dev: boolean; onNext: (me: Me) => void }) {
  const up = useUpload('/kyc/selfie');
  const { busy, error, run } = useAction();
  const submit = () => run(async () => onNext(await up.send()));
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

/* ---------------- done ---------------- */
function DoneStep({ header }: { header: React.ReactNode }) {
  const { me } = useStore();
  const nav = useNavigate();
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
        <button className="btn btn-primary btn-block" style={{ height: 56 }} onClick={() => nav('/fund')}>Add money</button>
        <button className="btn btn-soft btn-block" onClick={() => nav('/')}>Go to Home</button>
      </div>
    </>
  );
}

/** The nudge shown on Home, Add money and Profile until someone has verified. */
export function VerifyCard({ compact = false }: { compact?: boolean }) {
  const { me } = useStore();
  const nav = useNavigate();
  const s = me?.user?.kyc_status;
  if (!s || s === 'verified') return null;
  const started = s !== 'not_started';
  return (
    <div className="card verify-card">
      <span className="vc-ic">🪪</span>
      <div style={{ minWidth: 0 }}>
        <b>{started ? 'Finish verifying your identity' : 'Verify your identity'}</b>
        {!compact && <p className="small muted" style={{ margin: '2px 0 0' }}>Needed before you can add money and start sending. Your NIN or BVN, a photo of your ID and a selfie. About 2 minutes.</p>}
      </div>
      <button className="btn btn-primary" onClick={() => nav('/verify')}>{started ? 'Continue' : 'Verify'}</button>
    </div>
  );
}
