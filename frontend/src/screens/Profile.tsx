import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { N } from '../lib/format';
import { createPasskey, passkeysSupported } from '../lib/passkey';
import { useStore } from '../lib/store';
import type { Me } from '../lib/types';
import { PinDots, PinPad, Switch, useAction } from '../components/ui';
import { openAppearance } from './Appearance';
import { AddRecipient } from './NewPlan';

type Row = { icon: string; title: string; sub?: string; val?: React.ReactNode; on?: boolean; onClick?: () => void; danger?: boolean };
const SetRow = ({ icon, title, sub, val, on, onClick, danger }: Row) => (
  <button className={`set-row ${danger ? 'danger' : ''} ${on !== undefined || !onClick ? 'no-arrow' : ''}`} onClick={onClick} style={!onClick ? { cursor: 'default' } : undefined}>
    <span className="si">{icon}</span><span style={{ minWidth: 0 }}><b>{title}</b>{sub && <span className="sub">{sub}</span>}</span>
    {on !== undefined ? <Switch on={on} label={title} onChange={() => onClick?.()} /> : <span className="val">{val}</span>}
  </button>
);

export default function Profile() {
  const store = useStore();
  const { me, recipients, setMe, refreshMe, reload, toast, openSheet, closeSheet, look } = store;
  const nav = useNavigate();
  const u = me?.user;
  if (!u) return null;
  const save = async (patch: Record<string, unknown>, msg: string) => { setMe(await api.patch<Me>('/me/settings', patch)); await reload(); toast(msg); };
  const fa = u.funding_account;
  const people = recipients.filter((r) => !r.is_self && !r.label.endsWith('(removed)'));

  const faceId = async () => {
    try {
      if (u.has_face_id) { setMe(await api.del<Me>('/auth/passkey')); toast("Face ID is off. You'll use your PIN."); return; }
      if (!passkeysSupported()) { toast("This device doesn't support Face ID for websites."); return; }
      const credential = await createPasskey(await api.post('/auth/passkey/register/options'));
      setMe(await api.post<Me>('/auth/passkey/register/verify', { credential, device_label: navigator.platform || 'This device' }));
      toast('Face ID is on');
    } catch (e: any) { toast(e?.name === 'NotAllowedError' ? 'Face ID was not turned on.' : e.message); }
  };

  const capSheet = () => openSheet(<>
    <h3>Daily sending limit</h3>
    <p className="small muted" style={{ marginTop: -6 }}>A safety net. If drips would go over this in one day, the extra ones wait and we tell you.</p>
    <div className="opt-list">{[2_000_000, 5_000_000, 10_000_000, 20_000_000, null].map((v) => (
      <button key={String(v)} className="opt" aria-pressed={u.daily_cap_kobo === v} onClick={() => { closeSheet(); save({ daily_cap_kobo: v }, v ? `Daily limit set to ${N(v)}` : 'Daily limit removed'); }}>
        <span>🧢</span><span><b>{v ? `${N(v)} a day` : 'No limit'}</b></span><span className="check">✓</span></button>
    ))}</div></>);

  const peopleSheet = () => openSheet(<PeopleSheet />);
  const signOut = () => openSheet(<>
    <h3>Sign out?</h3>
    <p className="muted" style={{ marginTop: -6 }}>Your plans keep running. To get back in on this device you'll need a texted code and your PIN.</p>
    <div style={{ display: 'flex', gap: 8 }}><button className="btn btn-soft" style={{ flex: 1 }} onClick={closeSheet}>Stay signed in</button>
      <button className="btn btn-danger" style={{ flex: 1 }} onClick={async () => { closeSheet(); await api.post('/auth/signout'); await refreshMe(); nav('/'); }}>Sign out</button></div></>);

  return (
    <div className="stack">
      <div className="close-row"><button className="link" onClick={() => nav('/')}>← Home</button><span className="eyebrow">Profile</span></div>
      <div className="cols cols-profile"><div className="col stack">
        <div className="card prof-head">
          <span className="avatar lg">{(u.first_name[0] ?? '') + (u.last_name[0] ?? '')}</span>
          <h1>{u.first_name} {u.last_name}</h1>
          <span className="small muted">{u.phone_masked}</span>
          <span className="verified-pill">✓ Verified</span>
        </div>
        {fa && <div className="acct"><span className="small muted" style={{ fontWeight: 700 }}>Your SpenDrip account</span>
          <span className="acct-no num">{fa.account_number.replace(/(\d{4})(\d{3})(\d{3})/, '$1 $2 $3')}</span><span style={{ fontWeight: 700 }}>{fa.bank_name}</span>
          <button className="btn btn-soft" style={{ marginTop: 6 }} onClick={async () => { try { await navigator.clipboard.writeText(fa.account_number); toast('Account number copied'); } catch { toast(fa.account_number); } }}>Copy number</button></div>}
      </div><div className="col stack">
        <div className="group-h">Identity</div>
        <div className="list">
          <SetRow icon="🪪" title="NIN" sub={`•••• ••• ${u.nin_last4} · checked`} val={<span className="pill p-send">Verified</span>} />
          <SetRow icon="📄" title="ID document" sub="Front of your ID" val={<span className="pill p-send">Verified</span>} />
          <SetRow icon="🤳" title="Selfie" sub="Face matches your ID" val={<span className="pill p-send">Verified</span>} />
          <SetRow icon="📊" title="Account limits" sub="Set by your verification level" val="View" onClick={() => openSheet(<>
            <h3>Account limits</h3>
            <p className="muted">Your limits depend on your verification level. We're confirming the exact figures with our banking partner and will show them here.</p></>)} />
        </div>
        <div className="group-h">Security</div>
        <div className="list">
          <SetRow icon="🙂" title="Face ID" sub="Open the app without typing your PIN" on={u.has_face_id} onClick={faceId} />
          <SetRow icon="🔢" title="Change PIN" onClick={() => openSheet(<ChangePin />)} />
          <SetRow icon="🔒" title="Lock app now" onClick={async () => { await api.post('/auth/lock'); await refreshMe(); }} />
        </div>
        <div className="group-h">Money</div>
        <div className="list">
          <SetRow icon="🧢" title="Daily sending limit" sub="Most SpenDrip can send in one day" val={u.daily_cap_kobo ? N(u.daily_cap_kobo) : 'No limit'} onClick={capSheet} />
          <SetRow icon="⏸" title="Pause everything" sub={u.paused_all ? 'No drips will go out until you turn this off' : 'Stop all drips at once. Nothing is deleted.'} on={u.paused_all}
            onClick={() => save({ paused_all: !u.paused_all }, u.paused_all ? 'All drips are back on' : 'All drips paused')} />
          <SetRow icon="👥" title="People" sub={people.map((r) => r.label).join(', ') || 'No one yet'} val={String(people.length)} onClick={peopleSheet} />
          <SetRow icon="🧾" title="Transfer fee" sub="₦50 per drip, always included in your totals" />
        </div>
        <div className="group-h">Notifications</div>
        <div className="list">
          <SetRow icon="🔔" title="Push notifications" sub="When money is sent or added" on={u.notify_push} onClick={() => save({ notify_push: !u.notify_push }, 'Saved')} />
          <SetRow icon="💬" title="WhatsApp the people you pay" sub="They get a message when money lands" on={u.notify_whatsapp_recipients} onClick={() => save({ notify_whatsapp_recipients: !u.notify_whatsapp_recipients }, 'Saved')} />
          <SetRow icon="🌙" title="Tomorrow's drips" sub="A summary at 8 PM" on={u.notify_daily_summary} onClick={() => save({ notify_daily_summary: !u.notify_daily_summary }, 'Saved')} />
          <SetRow icon="⚠️" title="Low balance warning" sub="When a drip is about to wait" on={u.notify_low_balance} onClick={() => save({ notify_low_balance: !u.notify_low_balance }, 'Saved')} />
        </div>
        <div className="group-h">App</div>
        <div className="list">
          <SetRow icon="🎨" title="Appearance" val={{ themed: 'Themed', light: 'Light', dark: 'Dark' }[look]} onClick={() => openAppearance(store)} />
          <SetRow icon="🚪" title="Sign out" danger onClick={signOut} />
        </div>
        <p className="small muted" style={{ textAlign: 'center', margin: '4px 0 0' }}>SpenDrip 0.2{me?.dev_tools ? ' · test mode' : ''}</p>
      </div></div>
    </div>
  );
}

function ChangePin() {
  const { closeSheet, toast } = useStore();
  const [stage, setStage] = useState<'cur' | 'new' | 'conf'>('cur');
  const [pin, setPin] = useState('');
  const [cur, setCur] = useState('');
  const [next, setNext] = useState('');
  const { error, setError, run } = useAction();
  const change = (v: string) => {
    setPin(v); setError('');
    if (v.length < 4) return;
    window.setTimeout(() => {
      if (stage === 'cur') { setCur(v); setStage('new'); setPin(''); return; }
      if (stage === 'new') { setNext(v); setStage('conf'); setPin(''); return; }
      if (v !== next) { setError("PINs don't match. Try again."); setStage('new'); setPin(''); return; }
      run(async () => { try { await api.post('/auth/pin/change', { current: cur, new: v }); closeSheet(); toast('PIN changed'); } catch (e) { setStage('cur'); setPin(''); throw e; } });
    }, 180);
  };
  return (
    <>
      <h3 style={{ textAlign: 'center' }}>{{ cur: 'Enter your current PIN', new: 'Choose a new PIN', conf: 'Enter the new PIN again' }[stage]}</h3>
      <PinDots n={pin.length} bad={!!error} />
      <p className="err">{error}</p>
      <PinPad value={pin} onChange={change} />
    </>
  );
}

function PeopleSheet() {
  const { recipients, reload, toast } = useStore();
  const [adding, setAdding] = useState(false);
  const [err, setErr] = useState('');
  if (adding) return <AddRecipient onSaved={() => setAdding(false)} />;
  const remove = async (id: number) => {
    setErr('');
    try { await api.del(`/recipients/${id}`); await reload(); toast('Removed'); } catch (e: any) { setErr(e.message); }
  };
  return (
    <>
      <h3>People you pay</h3>
      {err && <div className="error-card" style={{ marginBottom: 10 }}>{err}</div>}
      <div className="list">
        {recipients.filter((r) => !r.label.endsWith('(removed)')).map((r) => (
          <div key={r.id} className="set-row no-arrow"><span className="si">{r.is_self ? '🙋' : r.label[0]}</span>
            <span><b>{r.label}</b><span className="sub">{r.verified_account_name} · {r.bank_name} ••{r.account_last4}{r.whatsapp ? ' · WhatsApp on' : ''}</span></span>
            {!r.is_self ? <button className="link small" style={{ color: 'var(--red)' }} onClick={() => remove(r.id)}>Remove</button> : <span />}</div>
        ))}
      </div>
      <button className="btn btn-soft btn-block" style={{ marginTop: 12 }} onClick={() => setAdding(true)}>＋ Add someone</button>
    </>
  );
}
