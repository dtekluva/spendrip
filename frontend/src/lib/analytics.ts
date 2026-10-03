/**
 * Cookieless analytics (Umami at stats.spendrip.com) for the sign-up funnel, plus first-touch attribution:
 * spendrip.com links arrive with ?src=…&lp=…, which we keep in localStorage and send with sign-up.
 */
declare global { interface Window { umami?: { track: (name: string, data?: Record<string, unknown>) => void } } }

const KEY = 'sd-src';
type Source = { s: string; p: string };

export function captureSource(): void {
  try {
    const q = new URLSearchParams(location.search);
    const s = q.get('src'), p = q.get('lp');
    if (s && !localStorage.getItem(KEY)) localStorage.setItem(KEY, JSON.stringify({ s: s.slice(0, 80), p: (p ?? '').slice(0, 120) }));
    if (s || p) {  // tidy the address bar
      q.delete('src'); q.delete('lp');
      history.replaceState(null, '', location.pathname + (q.toString() ? `?${q}` : '') + location.hash);
    }
  } catch { /* storage blocked: attribution is best-effort */ }
}

export function source(): Source {
  try { return JSON.parse(localStorage.getItem(KEY) || 'null') ?? { s: 'direct', p: '' }; } catch { return { s: 'direct', p: '' }; }
}

/** Funnel events: signup_started, account_created, signup_completed, verified, plan_created, topup_completed. */
export function track(name: string, data: Record<string, unknown> = {}): void {
  try { window.umami?.track(name, { source: source().s, ...data }); } catch { /* never break the app for analytics */ }
}
