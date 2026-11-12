/**
 * Installing SpenDrip on a phone or computer (it's a web app, so "download" means adding it to the home screen).
 *
 * Chrome, Edge and Samsung Internet fire `beforeinstallprompt` once the app qualifies; we keep that event so our own
 * Install button can show the browser's install dialog. iPhones never fire it: there, the only way is Share → Add to
 * Home Screen, so we show those steps instead. Imported from main.tsx before anything renders, so the event isn't missed.
 */
import { useEffect, useState } from 'react';
import { track } from './analytics';

type PromptEvent = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }> };

let deferred: PromptEvent | null = null;
let justInstalled = false;
const listeners = new Set<() => void>();
const changed = () => listeners.forEach((l) => l());

if (typeof window !== 'undefined') {
  window.addEventListener('beforeinstallprompt', (e) => { e.preventDefault(); deferred = e as PromptEvent; changed(); });
  window.addEventListener('appinstalled', () => { deferred = null; justInstalled = true; track('app_installed'); changed(); });
}

/** Already running as the installed app (home screen icon), so there's nothing to install. */
export const isInstalled = () => justInstalled || (typeof window !== 'undefined' && (
  window.matchMedia?.('(display-mode: standalone)').matches || window.matchMedia?.('(display-mode: window-controls-overlay)').matches
  || (navigator as Navigator & { standalone?: boolean }).standalone === true));

/**
 * How this browser installs apps:
 *  prompt      we can show the browser's own install dialog (Android Chrome, Edge, desktop Chrome)
 *  ios         iPhone/iPad Safari, or Chrome/Edge/Firefox on iOS 16.4+: Share → Add to Home Screen
 *  ios-safari  an iPhone in-app browser (WhatsApp, Instagram, Facebook…) that can't install: open in Safari first
 *  in-app      the same on Android: open in Chrome first
 *  android     Android browser that hasn't offered the dialog (yet): ⋮ menu → Install app / Add to Home screen
 *  desktop     a computer browser without the dialog (Firefox, Safari): explain, or suggest Chrome/Edge
 */
export type InstallWay = 'prompt' | 'ios' | 'ios-safari' | 'in-app' | 'android' | 'desktop';

export function installWay(): InstallWay {
  const ua = navigator.userAgent;
  const ios = /iPhone|iPad|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const inApp = /FBAN|FBAV|FB_IAB|Instagram|Line\/|Snapchat|TikTok|Twitter|LinkedInApp|WhatsApp|GSA\/|; wv\)/.test(ua);
  if (deferred) return 'prompt';
  if (ios) return inApp ? 'ios-safari' : 'ios';
  if (/Android/.test(ua)) return inApp ? 'in-app' : 'android';
  return 'desktop';
}

/** Show the browser's install dialog. Resolves true if the person accepted. */
export async function promptInstall(): Promise<boolean> {
  const e = deferred;
  if (!e) return false;
  track('install_prompted');
  await e.prompt();
  const { outcome } = await e.userChoice;
  deferred = null;  // each event can only be used once; the browser fires a new one if it's offered again
  changed();
  if (outcome === 'accepted') track('install_accepted');
  return outcome === 'accepted';
}

/** Re-renders when the install state changes (the dialog becomes available, or the app gets installed). */
export function useInstall() {
  const [, tick] = useState(0);
  useEffect(() => { const l = () => tick((n) => n + 1); listeners.add(l); return () => { listeners.delete(l); }; }, []);
  return { installed: isInstalled(), way: installWay() };
}

// The Home card can be closed; it comes back after a while, since installing is the best way to use SpenDrip.
const HIDE_KEY = 'sd-install-hidden';
const HIDE_DAYS = 21;
export function cardHidden(): boolean {
  try { return Date.now() - Number(localStorage.getItem(HIDE_KEY) || 0) < HIDE_DAYS * 864e5; } catch { return false; }
}
export function hideCard(): void {
  try { localStorage.setItem(HIDE_KEY, String(Date.now())); } catch { /* storage blocked: it just shows again */ }
}
