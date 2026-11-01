import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useStore } from '../lib/store';
import { Icon, Wordmark } from './ui';
import { Ic, type IconName } from '../icons';
import { openAppearance } from '../screens/Appearance';

export default function Nav() {
  const nav = useNavigate();
  const loc = useLocation();
  const store = useStore();
  const initials = ((store.me?.user?.first_name?.[0] ?? '') + (store.me?.user?.last_name?.[0] ?? '')).toUpperCase();
  // The selected tab's icon switches to its filled weight.
  const tab = (to: string, label: string, icon: IconName, extra = '') => {
    const on = to === '/' ? loc.pathname === '/' : loc.pathname.startsWith(to);
    return (
      <NavLink to={to} end={to === '/'} className={`tab ${extra}`} aria-current={on ? 'page' : undefined}>
        <Ic name={icon} weight={on ? 'f' : 'r'} />{label}
      </NavLink>
    );
  };
  // The plan builder is a focused screen: no bottom tab bar on phones (it would sit on the Start button), but the
  // desktop sidebar stays.
  const focused = loc.pathname.startsWith('/plans/new') || loc.pathname.endsWith('/edit');
  return (
    <nav className={`nav ${focused ? 'nav-focused' : ''}`} aria-label="Main">
      <Wordmark className="nav-brand" />
      {tab('/', 'Home', 'home')}
      {tab('/plans', 'Plans', 'plans')}
      <button className="fab" aria-label="New plan" onClick={() => nav('/plans/new')}>{Icon.plus}<span className="fab-label">New plan</span></button>
      {tab('/activity', 'Activity', 'activity')}
      {tab('/fund', 'Add money', 'fund')}
      {tab('/finance', 'Finance', 'finance', 'web-only')}
      {tab('/people', 'People', 'people', 'web-only')}
      {tab('/calendar', 'Calendar', 'calendar', 'web-only')}
      <NavLink to="/settings" className="tab web-only nav-foot"><Ic name="settings" weight={loc.pathname.startsWith('/settings') ? 'f' : 'r'} />Settings</NavLink>
      <NavLink to="/profile" className="tab web-only"><span className="avatar sm">{initials}</span>Profile</NavLink>
      <button className="tab web-only" onClick={() => openAppearance(store)}>{Icon.look}Appearance</button>
    </nav>
  );
}
