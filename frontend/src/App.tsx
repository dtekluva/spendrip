import { useCallback, useEffect, useRef, useState } from 'react';
import { Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import { onAuthProblem } from './lib/api';
import { useStore } from './lib/store';
import type { Me } from './lib/types';
import Nav from './components/Nav';
import Splash from './screens/Splash';
import Welcome from './screens/Welcome';
import Signup from './screens/Signup';
import SignIn from './screens/SignIn';
import Lock from './screens/Lock';
import Home from './screens/Home';
import Plans from './screens/Plans';
import NewPlan from './screens/NewPlan';
import Calendar from './screens/Calendar';
import Fund from './screens/Fund';
import Activity from './screens/Activity';
import Profile from './screens/Profile';
import KoboGallery from './screens/KoboGallery';
import CardReturn from './screens/CardTopUp';
import Verify from './screens/Verify';

const SEEN = 'sd-seen-splash';
const seenBefore = () => { try { return localStorage.getItem(SEEN) === '1'; } catch { return false; } };

export default function App() {
  const { me, refreshMe, setMe, reload } = useStore();
  const nav = useNavigate();
  const [splash, setSplash] = useState(true);
  const quick = useRef(seenBefore());
  const [flow, setFlow] = useState<'welcome' | 'signup' | 'signin' | 'forgot'>('welcome');
  const [inSignup, setInSignup] = useState(false);
  const [bootError, setBootError] = useState('');

  const boot = useCallback(() => refreshMe().catch((e) => setBootError(e.message)), [refreshMe]);
  useEffect(() => { boot(); return onAuthProblem(() => { refreshMe().catch(() => {}); }); }, [boot, refreshMe]);

  const ready = !!me?.signed_in && !me.locked && !!me.user?.has_pin && !!me.user?.has_name && !inSignup;
  useEffect(() => { if (ready) reload().catch(() => {}); }, [ready, reload]);
  useEffect(() => { if (me?.signup?.step) { setFlow('signup'); setInSignup(true); } }, [me?.signup?.step]);
  // Signed in but no name or PIN yet (e.g. the app was reopened mid sign-up): finish those before entering the app.
  useEffect(() => { if (me?.signed_in && me.user && (!me.user.has_pin || !me.user.has_name)) setInSignup(true); }, [me?.signed_in, me?.user?.has_pin, me?.user?.has_name]); // eslint-disable-line react-hooks/exhaustive-deps

  const endSplash = useCallback(() => { setSplash(false); try { localStorage.setItem(SEEN, '1'); } catch { /* ignore */ } }, []);
  const signedIn = (m: Me) => { setMe(m); setFlow('welcome'); nav('/'); };

  if (splash) return <Splash quick={quick.current} onDone={endSplash} />;
  if (!me) return <div className="boot">{bootError ? <span>{bootError} <button className="link" onClick={boot}>Try again</button></span> : 'Loading…'}</div>;

  if (!me.signed_in) {
    if (flow === 'signin' || flow === 'forgot') return <SignIn forgot={flow === 'forgot'} onBack={() => setFlow('welcome')} onDone={signedIn} />;
    if (flow === 'signup') return <Signup onExit={() => setFlow('welcome')} onFinished={() => {}} />;
    return <Welcome onCreate={() => { setInSignup(true); setFlow('signup'); }} onSignIn={() => setFlow('signin')} />;
  }
  if (inSignup || !me.user?.has_pin || !me.user?.has_name) {
    return <Signup onExit={() => {}} onFinished={(to) => { setInSignup(false); nav(to === 'new' ? '/plans/new' : to === 'verify' ? '/verify' : '/'); }} />;
  }
  if (me.locked) {
    if (flow === 'forgot') return <SignIn forgot onBack={() => setFlow('welcome')} onDone={signedIn} />;
    return <Lock onUnlocked={(m) => { setMe(m); reload(); }} onForgot={() => setFlow('forgot')} />;
  }

  return (
    <div className="app">
      <div className="screens">
        <section className="screen">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/plans" element={<Plans />} />
            <Route path="/plans/new" element={<NewPlan />} />
            <Route path="/plans/:id/edit" element={<NewPlan />} />
            <Route path="/calendar" element={<Calendar />} />
            <Route path="/fund" element={<Fund />} />
            <Route path="/fund/card" element={<CardReturn />} />
            <Route path="/activity" element={<Activity />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/kobo" element={<KoboGallery />} />
            <Route path="/verify" element={<Verify />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </section>
      </div>
      <Nav />
    </div>
  );
}
