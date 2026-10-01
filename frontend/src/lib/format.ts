import type { Plan } from './types';

export const TZ = 'Africa/Lagos';
export const WD = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
export const ISO_WD = ['', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
export const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
export const MONL = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

export const N = (kobo: number) => '₦' + Math.round(kobo / 100).toLocaleString('en-NG');
export const kN = (kobo: number) => (kobo >= 100_000 ? '₦' + String(Math.round(kobo / 10_000) / 10).replace(/\.0$/, '') + 'k' : N(kobo));
export const ord = (n: number) => n + (['th', 'st', 'nd', 'rd'][((n % 100) - 20) % 10] || ['th', 'st', 'nd', 'rd'][n % 100] || 'th');

/** Wall-clock parts in Lagos, whatever the device's own time zone is. */
export function lagos(d: Date | string) {
  const date = typeof d === 'string' ? new Date(d) : d;
  const p = Object.fromEntries(new Intl.DateTimeFormat('en-GB', {
    timeZone: TZ, year: 'numeric', month: 'numeric', day: 'numeric', hour: 'numeric', minute: 'numeric', weekday: 'short', hourCycle: 'h23',
  }).formatToParts(date).map((x) => [x.type, x.value]));
  const wd = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].indexOf(p.weekday);
  return { y: +p.year, m: +p.month, d: +p.day, h: +p.hour, min: +p.minute, wd, date };
}
export const dayKey = (d: Date | string) => { const x = lagos(d); return `${x.y}-${x.m}-${x.d}`; };

export function fmtTime(t: string | Date): string {
  let h: number, m: number;
  if (typeof t === 'string' && /^\d\d:\d\d$/.test(t)) [h, m] = t.split(':').map(Number) as [number, number];
  else { const x = lagos(t); h = x.h; m = x.min; }
  return `${h % 12 || 12}:${String(m).padStart(2, '0')} ${h >= 12 ? 'PM' : 'AM'}`;
}

export function dayLabel(d: Date | string): string {
  const x = lagos(d), now = lagos(new Date());
  const tomorrow = lagos(new Date(Date.now() + 86_400_000));
  if (x.y === now.y && x.m === now.m && x.d === now.d) return 'Today';
  if (x.y === tomorrow.y && x.m === tomorrow.m && x.d === tomorrow.d) return 'Tomorrow';
  if (x.y === now.y) {
    const yest = lagos(new Date(Date.now() - 86_400_000));
    if (x.m === yest.m && x.d === yest.d) return 'Yesterday';
  }
  return `${WD[x.wd]!.slice(0, 3)} ${x.d} ${MON[x.m - 1]}`;
}

export function cadence(p: Pick<Plan, 'frequency' | 'weekday' | 'month_day' | 'month_day_last'>): string {
  if (p.frequency === 'daily') return 'Every day';
  if (p.frequency === 'weekly') return 'Every ' + ISO_WD[p.weekday ?? 1];
  return p.month_day_last ? 'Last day of every month' : 'Monthly on the ' + ord(p.month_day ?? 1);
}

export function greet(): string {
  const h = lagos(new Date()).h;
  return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
}

export function countdown(at: string | Date): string {
  let s = Math.max(0, Math.floor((new Date(at).getTime() - Date.now()) / 1000));
  const d = Math.floor(s / 86400); s -= d * 86400;
  const h = Math.floor(s / 3600); s -= h * 3600;
  const m = Math.floor(s / 60); s -= m * 60;
  return d ? `in ${d}d ${h}h ${m}m` : `in ${h}h ${String(m).padStart(2, '0')}m ${String(s).padStart(2, '0')}s`;
}
