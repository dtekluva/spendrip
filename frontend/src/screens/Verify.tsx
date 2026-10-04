import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { useStore } from '../lib/store';
import type { Me } from '../lib/types';
import { Icon, Spinner, useAction } from '../components/ui';
import Kobo, { KoboLoader } from '../components/Kobo';
import { track } from '../lib/analytics';
import { N } from '../lib/format';

/** Verify your identity, from inside the app: a photo of your ID, then three face angles. Unlocks adding money and sending it. */
type Step = 'document' | 'liveness' | 'done';
const STEPS: Step[] = ['document', 'liveness'];
const ID_TYPES = [['nin', 'NIN slip / ID card'], ['dl', "Driver's licence"], ['vc', "Voter's card"], ['pp', 'Passport']] as const;

function startStep(me: Me | null): Step {
  const s = me?.user?.kyc_status;
  return s === 'verified' ? 'done' : s === 'doc_uploaded' ? 'liveness' : 'document';
}

export default function Verify() {
  const { me, setMe, reload, confetti } = useStore();
  const nav = useNavigate();
  const [step, setStep] = useState<Step>(() => startStep(me));
  const dev = !!me?.dev_tools;
  const i = Math.max(0, STEPS.indexOf(step));
  const back = () => (step === 'liveness' ? setStep('document') : nav(-1));
  const header = (
    <>
      <div className="kyc-top">
        {step === 'done' ? <span /> : <button className="icon-btn" aria-label="Back" onClick={back}>{Icon.back}</button>}
        <span className="small muted" style={{ fontWeight: 700 }}>{step === 'done' ? '' : `Verify your identity · ${i + 1} of 2`}</span>
      </div>
      {step !== 'done' && <div className="kyc-prog">{STEPS.map((s, k) => <i key={s} className={k <= i ? 'on' : ''} />)}</div>}
    </>
  );
  return (
    <div className="kyc verify" data-no-replay={step === 'done' ? undefined : ''}>  {/* ID photos and selfies are never recorded */}
      <div className="kyc-inner" key={step}>
        {step === 'document' && <DocStep header={header} dev={dev} onNext={() => setStep('liveness')} />}
        {step === 'liveness' && <LivenessStep header={header} dev={dev} onNext={async (m) => { setMe(m); await reload(); confetti(); setStep('done'); }} />}
        {step === 'done' && <DoneStep header={header} />}
      </div>
    </div>
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

/** Phone photos are huge (and sometimes HEIC). Re-encode as JPEG, at most 1600px on the long side, before upload. */
async function shrink(file: Blob, max = 1600): Promise<Blob> {
  try {
    const bmp = await createImageBitmap(file);
    const k = Math.min(1, max / Math.max(bmp.width, bmp.height));
    const c = document.createElement('canvas');
    c.width = Math.round(bmp.width * k); c.height = Math.round(bmp.height * k);
    c.getContext('2d')!.drawImage(bmp, 0, 0, c.width, c.height);
    return await new Promise<Blob>((r) => c.toBlob((b) => r(b ?? file), 'image/jpeg', 0.85));
  } catch {
    return file;  // the browser can't decode it; send it as it is
  }
}

function useUpload(path: string, extra: Record<string, string> = {}) {
  const [preview, setPreview] = useState('');
  const [blob, setBlob] = useState<Blob | null>(null);
  const take = (b: Blob) => { shrink(b).then((x) => { setBlob(x); setPreview(URL.createObjectURL(x)); }); };
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

/* ---------------- step 1: ID ---------------- */
/** Back camera with an ID-card-shaped guide (85.6 × 54 mm). The photo is cropped to the guide, plus a small margin. */
function IdCam({ onShot, onCancel }: { onShot: (b: Blob) => void; onCancel: () => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const frame = useRef<HTMLDivElement>(null);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let s: MediaStream | null = null;
    if (!navigator.mediaDevices?.getUserMedia) { setFailed(true); return; }
    navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 }, height: { ideal: 1440 } }, audio: false })
      .then((m) => { s = m; if (video.current) { video.current.srcObject = m; video.current.onloadedmetadata = () => setReady(true); } })
      .catch(() => setFailed(true));
    return () => s?.getTracks().forEach((t) => t.stop());
  }, []);
  const snap = () => {
    const v = video.current, f = frame.current;
    if (!v || !f || !v.videoWidth) return;
    const vr = v.getBoundingClientRect(), fr = f.getBoundingClientRect();
    const scale = Math.max(vr.width / v.videoWidth, vr.height / v.videoHeight);  // object-fit: cover
    const offX = (vr.width - v.videoWidth * scale) / 2, offY = (vr.height - v.videoHeight * scale) / 2;
    const pad = 0.07;
    let w = fr.width / scale, h = fr.height / scale;
    let x = (fr.left - vr.left - offX) / scale - w * pad, y = (fr.top - vr.top - offY) / scale - h * pad;
    w *= 1 + 2 * pad; h *= 1 + 2 * pad;
    x = Math.max(0, x); y = Math.max(0, y); w = Math.min(w, v.videoWidth - x); h = Math.min(h, v.videoHeight - y);
    const k = Math.min(1, 1600 / w);
    const c = document.createElement('canvas');
    c.width = Math.round(w * k); c.height = Math.round(h * k);
    c.getContext('2d')!.drawImage(v, x, y, w, h, 0, 0, c.width, c.height);
    c.toBlob((b) => b && onShot(b), 'image/jpeg', 0.9);
  };
  if (failed) return (
    <div className="stack" style={{ gap: 10 }}>
      <p className="small muted" style={{ margin: 0, textAlign: 'center' }}>We can't open the camera here. Use your phone's camera or pick a photo instead.</p>
      <FileButton primary label="📷 Open camera" capture="environment" onPick={onShot} />
      <FileButton label="Upload from gallery" onPick={onShot} />
    </div>
  );
  return (
    <div className="idcam">
      <div className="idcam-view">
        <video ref={video} autoPlay playsInline muted />
        <div ref={frame} className="idcam-frame" aria-hidden="true">
          <span className="corner tl" /><span className="corner tr" /><span className="corner bl" /><span className="corner br" />
        </div>
        <span className="idcam-tip">Fit the front of your ID inside the frame</span>
      </div>
      <button className="btn btn-primary btn-block" style={{ height: 56 }} disabled={!ready} onClick={snap}>Take photo</button>
      <button className="btn btn-soft btn-block" onClick={onCancel}>Cancel</button>
    </div>
  );
}

function DocStep({ header, dev, onNext }: { header: React.ReactNode; dev: boolean; onNext: () => void }) {
  const [idType, setIdType] = useState('nin');
  const [cam, setCam] = useState(false);
  const up = useUpload('/kyc/document', { id_type: idType });
  const { busy, error, run } = useAction();
  const shot = (b: Blob) => { setCam(false); up.take(b); };
  return (
    <>
      {header}
      <h2>Snap your ID</h2>
      <p className="lead">The front of your ID. Lay it flat in good light, and fit it inside the frame.</p>
      <div className="id-types" role="group" aria-label="ID type">
        {ID_TYPES.map(([k, l]) => <button key={k} aria-pressed={idType === k} onClick={() => setIdType(k)}>{l}</button>)}
      </div>
      {cam ? <IdCam onShot={shot} onCancel={() => setCam(false)} /> : <div className={`id-frame ${up.preview ? 'has' : ''}`}>
        {up.preview ? <img src={up.preview} alt="Your ID" /> : (
          <><div className="ghost"><i className="ph" /><span className="ln"><i style={{ width: '80%' }} /><i /><i style={{ width: '60%' }} /><i style={{ width: '70%' }} /></span></div>
            <span className="corner tl" /><span className="corner tr" /><span className="corner bl" /><span className="corner br" /></>
        )}
      </div>}
      {busy && <Spinner label="Checking your ID…" />}
      {error && <div className="error-card">{error}</div>}
      <div className="kyc-actions">
        {up.preview ? (
          <>
            <button className="btn btn-primary btn-block" style={{ height: 56 }} disabled={busy} onClick={() => run(async () => { await up.send(); onNext(); })}>Use this photo</button>
            <button className="btn btn-soft btn-block" onClick={() => { up.reset(); setCam(true); }}>Retake</button>
          </>
        ) : cam ? null : (
          <>
            <button className="btn btn-primary btn-block" style={{ height: 56 }} onClick={() => setCam(true)}>📷 Take a photo</button>
            <FileButton label="Upload from gallery" onPick={up.take} />
            {dev && <button className="demo-link" onClick={async () => up.take(await sampleBlob('id'))}>Use a sample ID (demo)</button>}
          </>
        )}
      </div>
    </>
  );
}

/* ---------------- step 2: three face angles ---------------- */
type Pose = 'front' | 'left' | 'right';
const POSE_TEXT: Record<Pose, { title: string; hint: string; arrow: string }> = {
  front: { title: 'Look straight at the camera', hint: 'Face in the oval, chin level.', arrow: '' },
  left: { title: 'Now turn your head to your left', hint: "Tap the button, then turn well to your left and hold. The photo takes itself after 3 seconds, so you don't need to look back at the screen.", arrow: '←' },
  right: { title: 'Now turn your head to your right', hint: "Tap the button, then turn well to your right and hold. The photo takes itself after 3 seconds, so you don't need to look back at the screen.", arrow: '→' },
};

function samplePose(pose: Pose): Promise<Blob> {
  const c = document.createElement('canvas');
  c.width = c.height = 480;
  const x = c.getContext('2d')!;
  x.fillStyle = '#FFD9A0'; x.fillRect(0, 0, 480, 480); x.fillStyle = '#7A4A2A';
  const dx = pose === 'left' ? -40 : pose === 'right' ? 40 : 0;
  x.beginPath(); x.ellipse(240 + dx, 210, 100, 120, 0, 0, Math.PI * 2); x.fill();
  return new Promise((r) => c.toBlob((b) => r(b!), 'image/jpeg', 0.85));
}

/** Live front-camera view with an oval guide. Camera only, on purpose: no photo picker, so a saved picture can't be used. */
function FaceCam({ pose, onShot }: { pose: Pose; onShot: (b: Blob) => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [failed, setFailed] = useState<'' | 'denied' | 'unsupported'>('');
  const [attempt, setAttempt] = useState(0);
  const [count, setCount] = useState(0);  // turn poses: seconds left before the photo takes itself
  const timer = useRef<number | null>(null);
  useEffect(() => () => { if (timer.current) window.clearInterval(timer.current); }, []);
  useEffect(() => {
    let s: MediaStream | null = null;
    setFailed('');
    if (!navigator.mediaDevices?.getUserMedia) { setFailed('unsupported'); return; }
    navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 960 } }, audio: false })
      .then((m) => { s = m; setStream(m); if (video.current) video.current.srcObject = m; })
      .catch(() => setFailed('denied'));
    return () => s?.getTracks().forEach((t) => t.stop());
  }, [attempt]);
  const snap = () => {
    const v = video.current;
    if (!v || !v.videoWidth) return;
    const c = document.createElement('canvas');
    const k = Math.min(1, 1280 / Math.max(v.videoWidth, v.videoHeight));
    c.width = Math.round(v.videoWidth * k); c.height = Math.round(v.videoHeight * k);
    c.getContext('2d')!.drawImage(v, 0, 0, c.width, c.height);  // un-mirrored, as the camera sees it
    c.toBlob((b) => b && onShot(b), 'image/jpeg', 0.88);
  };
  // A turned head can't see the screen, so turn poses use a countdown: tap, turn, hold, and the photo takes itself.
  const buzz = (ms: number) => { try { navigator.vibrate?.(ms); } catch { /* not supported */ } };
  const beep = (hz: number, ms: number) => {
    try {
      const a = new (window.AudioContext || (window as any).webkitAudioContext)();
      const o = a.createOscillator(); const g = a.createGain();
      o.frequency.value = hz; g.gain.value = 0.08; o.connect(g); g.connect(a.destination);
      o.start(); o.stop(a.currentTime + ms / 1000); o.onended = () => a.close();
    } catch { /* no sound */ }
  };
  const take = () => {
    if (pose === 'front') { snap(); return; }
    if (timer.current) return;
    let left = 3;
    setCount(left); buzz(60); beep(660, 90);
    timer.current = window.setInterval(() => {
      left -= 1;
      if (left > 0) { setCount(left); buzz(60); beep(660, 90); return; }
      window.clearInterval(timer.current!); timer.current = null;
      setCount(0); buzz(200); beep(990, 160);
      snap();
    }, 1000);
  };
  const t = POSE_TEXT[pose];
  if (failed) return (
    <div className="card stack" style={{ gap: 10, textAlign: 'center' }}>
      <b>{failed === 'denied' ? 'SpenDrip needs your camera for this step' : "This browser can't open the camera"}</b>
      <p className="small muted" style={{ margin: 0 }}>
        {failed === 'denied'
          ? 'Allow camera access when your browser asks. If you said no before, tap the camera or lock icon next to the address, choose Allow, then try again.'
          : 'Open SpenDrip in Chrome or Safari on your phone to take these photos.'}
        {' '}These photos have to be taken live, so you can't pick one from your gallery.
      </p>
      <button className="btn btn-primary btn-block" onClick={() => setAttempt((n) => n + 1)}>Try the camera again</button>
    </div>
  );
  return (
    <div className="facecam">
      <div className="facecam-view">
        <video ref={video} autoPlay playsInline muted />
        <div className={`oval pose-${pose}`} aria-hidden="true" />
        {t.arrow && <span className={`turn-arrow ${pose}`} aria-hidden="true">{t.arrow}</span>}
        {count > 0 && <span className="count" aria-live="assertive">{count}</span>}
      </div>
      <button className="btn btn-primary btn-block" style={{ height: 56 }} disabled={!stream || count > 0} onClick={take}>
        {pose === 'front' ? 'Take photo' : count > 0 ? `Keep turned… ${count}` : `Start, then turn ${pose}`}</button>
    </div>
  );
}

function LivenessStep({ header, dev, onNext }: { header: React.ReactNode; dev: boolean; onNext: (me: Me) => void }) {
  const [order, setOrder] = useState<Pose[] | null>(null);
  const [shots, setShots] = useState<Blob[]>([]);
  const { busy, error, setError, run } = useAction();
  const start = () => { setShots([]); setError(''); api.post<{ order: Pose[] }>('/kyc/liveness/start').then((r) => setOrder(r.order)).catch((e) => setError(e.message)); };
  useEffect(start, []); // eslint-disable-line react-hooks/exhaustive-deps
  const n = shots.length;
  const pose = order?.[n];
  const add = (b: Blob) => setShots((x) => [...x, b]);
  const submit = () => run(async () => {
    const fd = new FormData();
    shots.forEach((b, i) => fd.append(`image_${i}`, b, `pose-${i}.jpg`));
    try { const m = await api.post<Me>('/kyc/liveness', fd); track('verified'); onNext(m); }
    catch (e) { start(); throw e; }
  });
  useEffect(() => { if (order && n === order.length && !busy) submit(); }, [n]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <>
      {header}
      <h2>{pose ? POSE_TEXT[pose].title : busy ? 'Checking…' : 'Three quick photos'}</h2>
      <p className="lead">{pose ? POSE_TEXT[pose].hint : 'This shows it\'s really you, live, and not a photo of someone.'}</p>
      {order && (
        <div className="pose-steps" aria-label={`Photo ${Math.min(n + 1, 3)} of 3`}>
          {order.map((p, k) => <span key={k} className={k < n ? 'done' : k === n ? 'now' : ''}>{k < n ? '✓' : k + 1}</span>)}
        </div>
      )}
      {busy ? <KoboLoader mood="waiting" size={70} label="Checking your photos…" /> : error ? <div className="error-card">{error}</div> : null}
      {pose && !busy && <FaceCam key={`${n}-${pose}`} pose={pose} onShot={add} />}
      {dev && pose && !busy && <button className="demo-link" onClick={async () => add(await samplePose(pose))}>Use a sample photo (demo)</button>}
      <div className="lockline"><span>🔒</span><span>We only use these photos to check it's you. We don't share them with the people you pay.</span></div>
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
      <p className="lead" style={{ textAlign: 'center' }}>{fa ? 'Your SpenDrip account is ready. Send money to it any time to fund your plans.' : 'You can now add money by card or bank and start sending.'}</p>
      {me?.user?.limits && <p className="small muted" style={{ textAlign: 'center', margin: 0 }}>For now: up to {N(me.user.limits.max_drip_kobo)} per drip and {N(me.user.limits.max_balance_kobo)} in your balance.</p>}
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
        {!compact && <p className="small muted" style={{ margin: '2px 0 0' }}>Needed before you can add money and start sending. A photo of your ID and three quick face photos. About 2 minutes.</p>}
      </div>
      <button className="btn btn-primary" onClick={() => nav('/verify')}>{started ? 'Continue' : 'Verify'}</button>
    </div>
  );
}
