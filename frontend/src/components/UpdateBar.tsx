import { useEffect, useState } from 'react';
import { registerSW } from 'virtual:pwa-register';

/**
 * The app is cached for offline use, so a new version only arrives in the background. Check for one on launch,
 * whenever the app comes back to the foreground and every 30 minutes, then offer a Refresh (never forced).
 */
let update: ((reload?: boolean) => Promise<void>) | null = null;
const listeners = new Set<() => void>();

if (typeof window !== 'undefined' && 'serviceWorker' in navigator) {
  update = registerSW({
    immediate: true,
    // Right after launch nothing is in progress, so take the new version at once; later, offer a Refresh.
    onNeedRefresh() { if (performance.now() < 8000) applyUpdate(); else listeners.forEach((l) => l()); },
    onRegisteredSW(_url, reg) {
      if (!reg) return;
      const check = () => { reg.update().catch(() => {}); };
      window.setInterval(check, 30 * 60 * 1000);
      document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') check(); });
    },
  });
}

/** Switch to the waiting version and reload. Never gets stuck: if the hand-over isn't seen in 1.5 s, reload anyway. */
async function applyUpdate() {
  let done = false;
  const reload = () => { if (!done) { done = true; window.location.reload(); } };
  navigator.serviceWorker?.addEventListener('controllerchange', reload);
  try {
    const reg = await navigator.serviceWorker?.getRegistration();
    reg?.waiting?.postMessage({ type: 'SKIP_WAITING' });
    await update?.(true);
  } catch { /* fall through to the timed reload */ }
  window.setTimeout(reload, 1500);
}

export default function UpdateBar() {
  const [ready, setReady] = useState(false);
  useEffect(() => { const l = () => setReady(true); listeners.add(l); return () => { listeners.delete(l); }; }, []);
  if (!ready) return null;
  return (
    <div className="update-bar" role="status">
      <span>✨ A new version of SpenDrip is ready</span>
      <span className="acts">
        <button className="btn btn-primary" onClick={() => { setReady(false); applyUpdate(); }}>Refresh</button>
        <button className="link small" aria-label="Later" onClick={() => setReady(false)}>Later</button>
      </span>
    </div>
  );
}
