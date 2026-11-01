/*
 * SpenDrip's icons. One name per idea (see design/icons/manifest.json and README.md):
 *   <Ic name="calendar" />                 UI icon, regular weight, follows the text colour
 *   <Ic name="home" weight="f" />          filled, for selected states
 *   <Feature name="protected" />           duotone in SpenDrip blue and yellow, for features and empty states
 *   <PlanIcon emoji={plan.emoji} />        a plan's coloured tile; emoji the system doesn't know show as they are
 */
import { CATEGORY, EMOJI, PLANS, UI, type IconName, type PlanKey, type Weight } from './icons.gen';
import './icons.gen.css';

export type { IconName, PlanKey };

const svg = (inner: string, className: string, size?: number, label?: string) => (
  <svg className={className} viewBox="0 0 256 256" fill="currentColor" width={size} height={size}
    role={label ? 'img' : undefined} aria-label={label} aria-hidden={label ? undefined : true}
    dangerouslySetInnerHTML={{ __html: inner }} />
);

/** A UI icon. Falls back to the regular weight when the asked-for one isn't built. */
export function Ic({ name, weight = 'r', size, className = '', label }: { name: IconName; weight?: Weight; size?: number; className?: string; label?: string }) {
  const g = UI[name] as Partial<Record<Weight, string>>;
  return svg(g[weight] ?? g.r ?? g.f ?? g.d ?? '', `ic ${className}`, size, label);
}

/** A duotone feature icon: blue lines over a soft yellow fill (white and yellow on the navy look). */
export const Feature = ({ name, size, className = '' }: { name: IconName; size?: number; className?: string }) =>
  <Ic name={name} weight="d" size={size} className={`ic-duo ${className}`} />;

const plain = (e: string) => e.replace(/[\u{1F3FB}-\u{1F3FF}️]/gu, '');
const byKey = new Map(PLANS.map((p) => [p.key, p]));

/** What a stored emoji stands for, or undefined for emoji the system doesn't know (they keep showing as typed). */
export const planFor = (emoji?: string | null) => (emoji ? byKey.get(EMOJI[plain(emoji)]!) : undefined);
export const planForCategory = (category: string) => byKey.get(CATEGORY[category] ?? 'other')!;
export const PLAN_LIST = PLANS;

type TileSize = 'xs' | 'sm' | 'md';
/** A plan's tile: its icon on its colour. Pass the plan's emoji, or a finance category. */
export function PlanIcon({ emoji, category, size = 'md', className = '' }: { emoji?: string | null; category?: string; size?: TileSize; className?: string }) {
  const p = category ? planForCategory(category) : planFor(emoji);
  const cls = `tile pt ${size === 'md' ? '' : size} ${className}`;
  if (!p) return <span className={`${cls} pt-none`} aria-hidden="true">{emoji || '·'}</span>;
  return <span className={`${cls} pt-${p.hue}`} title={p.label}>{svg(p.glyph, 'ic', undefined)}</span>;
}

/** The chart colour for a finance category, matching its tile. */
export const categoryColour = (category: string) => planForCategory(category).chart;
