import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { api } from './api';
import type { Look, Me, Plan, Recipient, Summary } from './types';
import { KoboMoment, type KoboMood } from '../components/Kobo';

interface Store {
  me: Me | null;
  summary: Summary | null;
  plans: Plan[];
  recipients: Recipient[];
  loading: boolean;
  refreshMe: () => Promise<Me>;
  reload: () => Promise<void>;
  setMe: (m: Me) => void;
  look: Look;
  setLook: (l: Look) => void;
  // UI helpers
  toast: (msg: string, action?: { label: string; run: () => void }) => void;
  openSheet: (node: ReactNode) => void;
  closeSheet: () => void;
  confetti: () => void;
  /** Kobo pops up for a moment with one short line. */
  koboSay: (mood: KoboMood, text: string) => void;
}

const Ctx = createContext<Store>(null as unknown as Store);
export const useStore = () => useContext(Ctx);

const LOOK_KEY = 'sd-look';
const readLook = (): Look => { try { const v = localStorage.getItem(LOOK_KEY); if (v === 'light' || v === 'dark' || v === 'themed') return v; } catch { /* storage blocked */ } return 'themed'; };

export function StoreProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [recipients, setRecipients] = useState<Recipient[]>([]);
  const [loading, setLoading] = useState(false);
  const [look, setLookState] = useState<Look>(readLook);
  const [toastState, setToast] = useState<{ msg: string; action?: { label: string; run: () => void } } | null>(null);
  const [sheet, setSheet] = useState<ReactNode>(null);
  const [bursts, setBursts] = useState<number[]>([]);
  const toastTimer = useRef<number | undefined>(undefined);
  const [moment, setMoment] = useState<{ mood: KoboMood; text: string; id: number } | null>(null);
  const momentTimer = useRef<number | undefined>(undefined);

  const refreshMe = useCallback(async () => { const m = await api.get<Me>('/me'); setMe(m); return m; }, []);
  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const [s, p, r] = await Promise.all([api.get<Summary>('/summary'), api.get<Plan[]>('/plans'), api.get<Recipient[]>('/recipients')]);
      setSummary(s); setPlans(p); setRecipients(r);
    } finally { setLoading(false); }
  }, []);

  const setLook = useCallback((l: Look) => {
    setLookState(l);
    try { localStorage.setItem(LOOK_KEY, l); } catch { /* ignore */ }
    if (me?.signed_in && !me.locked) api.patch('/me/settings', { look: l }).catch(() => {});
  }, [me]);

  useEffect(() => { if (me?.user?.look && me.user.look !== look) setLookState(me.user.look); }, [me?.user?.look]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    document.documentElement.dataset.look = look;
    const color = { themed: '#0B1040', light: '#EFF1F5', dark: '#0E0F13' }[look];
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', color);
  }, [look]);

  const toast = useCallback((msg: string, action?: { label: string; run: () => void }) => {
    setToast({ msg, action });
    window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(null), 3800);
  }, []);
  const confetti = useCallback(() => {
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const id = Date.now(); setBursts((b) => [...b, id]); window.setTimeout(() => setBursts((b) => b.filter((x) => x !== id)), 2400);
  }, []);
  const closeSheet = useCallback(() => setSheet(null), []);
  const koboSay = useCallback((mood: KoboMood, text: string) => {
    setMoment({ mood, text, id: Date.now() });
    window.clearTimeout(momentTimer.current);
    momentTimer.current = window.setTimeout(() => setMoment(null), 2800);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setSheet(null); };
    window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey);
  }, []);

  const value = useMemo<Store>(() => ({ me, summary, plans, recipients, loading, refreshMe, reload, setMe, look, setLook, toast, openSheet: setSheet, closeSheet, confetti, koboSay }),
    [me, summary, plans, recipients, loading, refreshMe, reload, look, setLook, toast, closeSheet, confetti, koboSay]);

  return (
    <Ctx.Provider value={value}>
      <div className="phone" data-look={look}>
        <div className="device">
          {children}
          <div className={`scrim ${sheet ? 'show' : ''}`} onClick={closeSheet} />
          <div className={`sheet ${sheet ? 'show' : ''}`} role="dialog" aria-modal="true">
            <div className="grab" />
            {sheet}
          </div>
          <div className={`toast ${toastState ? 'show' : ''}`} role="status" aria-live="polite">
            <span>{toastState?.msg}</span>
            {toastState?.action && <button onClick={() => { toastState.action!.run(); setToast(null); }}>{toastState.action.label}</button>}
          </div>
          {bursts.map((id) => <Confetti key={id} />)}
          {moment && <KoboMoment key={moment.id} mood={moment.mood} text={moment.text} />}
        </div>
      </div>
    </Ctx.Provider>
  );
}

function Confetti() {
  const colors = ['var(--sun)', 'var(--hibiscus)', 'var(--mint)', 'var(--cobalt)', '#fff'];
  const bits = useMemo(() => Array.from({ length: 46 }, (_, i) => ({
    left: Math.random() * 100, bg: colors[i % colors.length], dx: Math.random() * 120 - 60, rot: Math.random() * 720 - 360,
    delay: Math.random() * 0.25, dur: 1.1 + Math.random() * 0.8,
  })), []); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="confetti">
      {bits.map((b, i) => (
        <i key={i} style={{ left: `${b.left}%`, background: b.bg, animationDelay: `${b.delay}s`, animationDuration: `${b.dur}s`,
          ['--dx' as any]: `${b.dx}px`, ['--rot' as any]: `${b.rot}deg` }} />
      ))}
    </div>
  );
}
