/**
 * Notifications on this phone or computer (web push). Turning them on asks the browser's permission, subscribes this
 * device with the server's key (me.push_key) and hands the subscription to the server, which sends to it
 * (backend/notifications/push.py). The service worker shows them (public/push-sw.js).
 *
 * iPhones only allow this once SpenDrip is on the home screen (iOS 16.4+), so there the first step is installing.
 * Browsers penalise sites that ask on load: we only ask when someone taps "Turn on".
 */
import { useCallback, useEffect, useState } from 'react';
import { api } from './api';
import { track } from './analytics';
import { isInstalled } from './install';

/** on: this device gets notifications · off: it could · blocked: denied in the browser · install-first: iPhone, add to home screen · unsupported */
export type PushState = 'on' | 'off' | 'blocked' | 'install-first' | 'unsupported';

const isIos = () => /iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
const supported = () => typeof window !== 'undefined' && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;

function keyBytes(b64: string): Uint8Array {
  const s = atob((b64 + '='.repeat((4 - (b64.length % 4)) % 4)).replace(/-/g, '+').replace(/_/g, '/'));
  return Uint8Array.from(s, (c) => c.charCodeAt(0));
}

/** The service worker, if there is one. Waits briefly: it isn't there in local development (vite dev). */
async function worker(): Promise<ServiceWorkerRegistration | null> {
  if (!supported()) return null;
  return Promise.race([navigator.serviceWorker.ready, new Promise<null>((r) => setTimeout(() => r(null), 4000))]);
}

async function current(): Promise<PushSubscription | null> {
  const reg = await navigator.serviceWorker?.getRegistration();
  return (await reg?.pushManager.getSubscription()) ?? null;
}

export async function pushState(key: string | undefined, on: boolean): Promise<PushState> {
  if (!supported() || !key) return isIos() && !isInstalled() ? 'install-first' : 'unsupported';
  if (Notification.permission === 'denied') return 'blocked';
  return on && Notification.permission === 'granted' && (await current()) ? 'on' : 'off';
}

const sameKey = (sub: PushSubscription, key: string) => {
  const k = sub.options?.applicationServerKey;
  if (!k) return true;  // older browsers don't say; assume it's ours
  const a = new Uint8Array(k), b = keyBytes(key);
  return a.length === b.length && a.every((v, i) => v === b[i]);
};

async function subscribe(key: string): Promise<boolean> {
  const reg = await worker();
  if (!reg) return false;
  let sub = await reg.pushManager.getSubscription();
  if (sub && !sameKey(sub, key)) { await sub.unsubscribe(); sub = null; }
  sub ??= await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(key) as BufferSource });
  await api.post('/push/devices', sub.toJSON());
  return true;
}

/** Ask, subscribe and tell the server. Must run straight from a tap (iPhone requires it). Returns the new state. */
export async function enablePush(key: string, from: string): Promise<PushState> {
  track('push_asked', { from });
  const perm = await Notification.requestPermission();
  if (perm !== 'granted') { track('push_declined', { from, perm }); return perm === 'denied' ? 'blocked' : 'off'; }
  if (!(await subscribe(key))) return 'unsupported';
  track('push_enabled', { from });
  changed();
  return 'on';
}

/** Stop notifications on this device. Returns how many devices the person still has them on. */
export async function disablePush(): Promise<number | null> {
  const sub = await current().catch(() => null);
  if (!sub) return null;
  const r = await api.del<{ devices: number }>('/push/devices', { endpoint: sub.endpoint }).catch(() => null);
  await sub.unsubscribe().catch(() => {});
  changed();
  return r?.devices ?? null;
}

/**
 * On each app start: keep the server's copy of this device's subscription fresh (browsers sometimes replace it), and
 * pick it up again if it was lost. Never asks: it only acts where permission was already given.
 */
export async function syncPush(key: string | undefined, on: boolean, devices: number) {
  if (!key || !on || !supported() || Notification.permission !== 'granted') return;
  const sub = await current();
  if (sub) await api.post('/push/devices', sub.toJSON()).catch(() => {});
  else if (devices > 0) await subscribe(key).catch(() => {});
}

// A tapped notification while the app is open: the service worker asks the app to show that screen.
type Opener = (path: string) => void;
let opener: Opener | null = null;
export const onNotificationOpen = (fn: Opener) => { opener = fn; return () => { if (opener === fn) opener = null; }; };
if (supported()) {
  navigator.serviceWorker.addEventListener('message', (e) => {
    if (e.data?.type === 'sd-open' && typeof e.data.path === 'string' && e.data.path.startsWith('/')) opener?.(e.data.path);
  });
}

const listeners = new Set<() => void>();
const changed = () => listeners.forEach((l) => l());

/** This device's notification state, kept up to date. */
export function usePush(key: string | undefined, on: boolean) {
  const [state, setState] = useState<PushState | null>(null);
  const refresh = useCallback(() => { pushState(key, on).then(setState).catch(() => setState('unsupported')); }, [key, on]);
  useEffect(() => { refresh(); listeners.add(refresh); return () => { listeners.delete(refresh); }; }, [refresh]);
  return state;
}
