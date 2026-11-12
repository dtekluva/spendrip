import { useState } from 'react';
import { Feature, Ic } from '../icons';
import { api } from '../lib/api';
import { cardHidden as installCardHidden, isInstalled } from '../lib/install';
import { disablePush, enablePush, usePush, type PushState } from '../lib/push';
import { useStore } from '../lib/store';
import { useOpenInstall } from './Install';

const device = () => (/Mobi|Android|iPhone|iPad/.test(navigator.userAgent) ? 'phone' : 'computer');

const SUB: Record<PushState, () => string> = {
  on: () => `On for this ${device()}: when money is sent or added`,
  off: () => 'When money is sent or added',
  blocked: () => "Blocked for SpenDrip in this browser's settings",
  'install-first': () => 'Add SpenDrip to your home screen first',
  unsupported: () => "This browser can't show notifications",
};

/** Everything the Settings row needs: its state, the line under it, and what a tap does. */
export function usePushSetting() {
  const { me, refreshMe, toast } = useStore();
  const openInstall = useOpenInstall();
  const u = me?.user;
  const state = usePush(me?.push_key, !!u?.notify_push);
  const [busy, setBusy] = useState(false);
  const run = (fn: () => Promise<void>) => async () => {
    if (busy) return;
    setBusy(true);
    try { await fn(); } catch (e) { toast((e as Error).message || "That didn't work. Try again."); } finally { setBusy(false); }
  };
  const toggle = run(async () => {
    if (!state || !me?.push_key) return;
    if (state === 'install-first') return openInstall('push');
    if (state === 'blocked') return toast("Notifications are blocked. Allow them for SpenDrip in your browser's site settings.");
    if (state === 'unsupported') return toast("This browser can't show notifications. Try Chrome, or install the app.");
    if (state === 'on') {
      const left = await disablePush();
      if (left === 0) await api.patch('/me/settings', { notify_push: false });
      await refreshMe();
      return toast(`Notifications off for this ${device()}`);
    }
    const s = await enablePush(me.push_key, 'settings');
    await refreshMe();
    toast(s === 'on' ? 'Notifications are on' : s === 'blocked' ? "Notifications are blocked. Allow them in your browser's site settings." : 'Notifications are still off');
  });
  const test = run(async () => { await api.post('/push/test'); toast('Sent. It should arrive in a few seconds.'); });
  return { state, sub: state ? SUB[state]() : 'When money is sent or added', on: state === 'on', toggle, test };
}

const HIDE_KEY = 'sd-push-hidden';
const HIDE_DAYS = 21;
const hidden = () => { try { return Date.now() - Number(localStorage.getItem(HIDE_KEY) || 0) < HIDE_DAYS * 864e5; } catch { return false; } };

/**
 * A card on Home asking to turn notifications on, where the browser could show them and hasn't been asked yet.
 * It waits until the install card is gone (on iPhone, installing comes first anyway).
 */
export function PushCard() {
  const { me, refreshMe, toast } = useStore();
  const state = usePush(me?.push_key, !!me?.user?.notify_push);
  const [gone, setGone] = useState(hidden);
  if (gone || state !== 'off' || Notification.permission !== 'default' || !me?.push_key) return null;
  if (!isInstalled() && !installCardHidden()) return null;
  const close = () => { try { localStorage.setItem(HIDE_KEY, String(Date.now())); } catch { /* shows again next time */ } setGone(true); };
  const turnOn = async () => {
    try {
      const s = await enablePush(me.push_key!, 'home');
      await refreshMe();
      if (s === 'on') toast("Notifications are on. We'll tell you when money moves.");
      else close();
    } catch (e) { toast((e as Error).message); }
  };
  return (
    <div className="install-card">
      <span className="feat-tile"><Feature name="bell" /></span>
      <button className="ic-body" onClick={turnOn}>
        <b>Money alerts</b>
        <span className="small muted">Get a notification when a drip is sent or money is added</span>
      </button>
      <button className="btn btn-primary ic-go" onClick={turnOn}>Turn on</button>
      <button className="icon-x" aria-label="Not now" onClick={close}><Ic name="close" /></button>
    </div>
  );
}
