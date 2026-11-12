import { useState, type ReactNode } from 'react';
import Kobo from './Kobo';
import { Feature, Ic } from '../icons';
import { useStore } from '../lib/store';
import { cardHidden, hideCard, promptInstall, useInstall, type InstallWay } from '../lib/install';
import { track } from '../lib/analytics';

const APP_URL = 'https://app.spendrip.com';

const Step = ({ n, children }: { n: number; children: ReactNode }) => (
  <li><span className="step-n">{n}</span><span className="step-t">{children}</span></li>
);

function CopyLink() {
  const [done, setDone] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(APP_URL); setDone(true); } catch { window.prompt('Copy this link', APP_URL); }
  };
  return <button className="btn btn-soft btn-block b-ic" onClick={copy}><Ic name={done ? 'check' : 'copy'} />{done ? 'Link copied' : 'Copy the link'}</button>;
}

const STEPS: Record<Exclude<InstallWay, 'prompt'>, { lead: string; steps: ReactNode[]; copy?: boolean }> = {
  ios: { lead: 'On iPhone, apps like SpenDrip are added from the Share menu. It takes a few seconds.', steps: [
    <>Tap <b className="b-ic">Share <Ic name="share-ios" /></b> at the bottom of the screen (at the top on iPad).</>,
    <>Scroll down and tap <b className="b-ic">Add to Home Screen <Ic name="add-home" /></b>.</>,
    <>Tap <b>Add</b>. SpenDrip appears on your home screen like any other app.</>] },
  'ios-safari': { lead: "This app's browser can't add SpenDrip to your home screen. Open it in Safari first.", copy: true, steps: [
    <>Tap <b className="b-ic">Copy the link</b> below.</>,
    <>Open <b>Safari</b>, paste it in the address bar and go.</>,
    <>Tap <b className="b-ic">Share <Ic name="share-ios" /></b>, then <b>Add to Home Screen</b>.</>] },
  'in-app': { lead: "This app's browser can't install SpenDrip. Open it in Chrome first.", copy: true, steps: [
    <>Tap <b className="b-ic"><Ic name="menu-dots" /></b> at the top and choose <b>Open in Chrome</b>, or copy the link below.</>,
    <>In Chrome, tap <b className="b-ic"><Ic name="menu-dots" /></b>, then <b>Install app</b> or <b>Add to Home screen</b>.</>,
    <>Tap <b>Install</b>.</>] },
  android: { lead: 'Your browser can add SpenDrip to your home screen from its menu.', steps: [
    <>Tap the menu <b className="b-ic"><Ic name="menu-dots" /></b> at the top right (at the bottom in some browsers).</>,
    <>Tap <b>Install app</b> or <b>Add to Home screen</b>.</>,
    <>Tap <b>Install</b>. SpenDrip appears with your other apps.</>] },
  desktop: { lead: 'You can install SpenDrip on this computer, or open app.spendrip.com on your phone.', steps: [
    <>In <b>Chrome</b> or <b>Edge</b>, click the install icon <b className="b-ic"><Ic name="install" /></b> at the right of the address bar.</>,
    <>In <b>Safari</b> on a Mac, choose <b>File → Add to Dock</b>.</>,
    <>On your phone, open <b>app.spendrip.com</b> and tap <b>Install the app</b> in Settings.</>] },
};

/** The sheet behind every "Install" button: the browser's own dialog where we can, otherwise the steps for this phone. */
export function InstallSheet() {
  const { closeSheet, toast } = useStore();
  const { installed, way } = useInstall();
  if (installed) {
    return <div className="install"><Kobo mood="happy" size={64} /><h3>SpenDrip is installed</h3>
      <p className="muted">You're using the app from your home screen. Nothing else to do.</p>
      <button className="btn btn-primary btn-block" onClick={closeSheet}>Done</button></div>;
  }
  if (way === 'prompt') {
    const install = async () => { if (await promptInstall()) { closeSheet(); toast('SpenDrip is on your home screen'); } };
    return <div className="install"><Kobo mood="happy" size={64} /><h3>Get the SpenDrip app</h3>
      <p className="muted">Open SpenDrip from your home screen, full screen, like any other app. It's free and takes a second.</p>
      <button className="btn btn-primary btn-block b-ic" style={{ height: 54 }} onClick={install}><Ic name="install" />Install SpenDrip</button>
      <button className="link" onClick={closeSheet}>Not now</button></div>;
  }
  const s = STEPS[way];
  return <div className="install"><Kobo mood="point" size={64} /><h3>Add SpenDrip to your home screen</h3>
    <p className="muted">{s.lead}</p>
    <ol className="install-steps">{s.steps.map((t, i) => <Step key={i} n={i + 1}>{t}</Step>)}</ol>
    {s.copy && <CopyLink />}
    <button className="btn btn-primary btn-block" onClick={closeSheet}>Got it</button></div>;
}

/** Opens the install sheet, and counts it. */
export function useOpenInstall() {
  const { openSheet } = useStore();
  return (from: string) => { track('install_opened', { from }); openSheet(<InstallSheet />); };
}

/** A card on Home until the app is installed; it can be closed for a few weeks. */
export function InstallCard() {
  const { installed } = useInstall();
  const open = useOpenInstall();
  const [hidden, setHidden] = useState(cardHidden);
  if (installed || hidden) return null;
  return (
    <div className="install-card">
      <span className="feat-tile"><Feature name="phone" /></span>
      <button className="ic-body" onClick={() => open('home')}>
        <b>Get the SpenDrip app</b>
        <span className="small muted">Add it to your home screen in a few seconds</span>
      </button>
      <button className="btn btn-primary ic-go" onClick={() => open('home')}>Install</button>
      <button className="icon-x" aria-label="Hide for now" onClick={() => { hideCard(); setHidden(true); }}><Ic name="close" /></button>
    </div>
  );
}
