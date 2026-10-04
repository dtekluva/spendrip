import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useStore } from '../lib/store';
import { Icon, Wordmark } from './ui';
import { openAppearance } from '../screens/Appearance';

export default function Nav() {
  const nav = useNavigate();
  const loc = useLocation();
  const store = useStore();
  const initials = ((store.me?.user?.first_name?.[0] ?? '') + (store.me?.user?.last_name?.[0] ?? '')).toUpperCase();
  const tab = (to: string, label: string, icon: React.ReactNode, extra = '') => (
    <NavLink to={to} end={to === '/'} className={`tab ${extra}`}
      aria-current={(to === '/' ? loc.pathname === '/' : loc.pathname.startsWith(to)) ? 'page' : undefined}>
      {icon}{label}
    </NavLink>
  );
  // The plan builder is a focused screen: no bottom tab bar on phones (it would sit on the Start button), but the
  // desktop sidebar stays.
  const focused = loc.pathname.startsWith('/plans/new') || loc.pathname.endsWith('/edit');
  return (
    <nav className={`nav ${focused ? 'nav-focused' : ''}`} aria-label="Main">
      <Wordmark className="nav-brand" />
      {tab('/', 'Home', Icon.home)}
      {tab('/plans', 'Plans', Icon.plans)}
      <button className="fab" aria-label="New plan" onClick={() => nav('/plans/new')}>{Icon.plus}<span className="fab-label">New plan</span></button>
      {tab('/activity', 'Activity', Icon.activity)}
      {tab('/fund', 'Add money', Icon.fund)}
      {tab('/people', 'People', Icon.person, 'web-only')}
      {tab('/calendar', 'Calendar', Icon.calendar, 'web-only')}
      <NavLink to="/profile" className="tab web-only nav-foot"><span className="avatar sm">{initials}</span>Profile</NavLink>
      <button className="tab web-only" onClick={() => openAppearance(store)}>{Icon.look}Appearance</button>
    </nav>
  );
}
