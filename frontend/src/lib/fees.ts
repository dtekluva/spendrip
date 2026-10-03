import type { FeeRules } from './types';

/** Mirrors backend engine/fees.py. The server sends its rules in /summary; these are the fallback. */
export const DEFAULT_FEES: FeeRules = {
  service_kobo: 5_000, stamp_duty_kobo: 5_000, stamp_duty_from_kobo: 1_000_000,
  provider_tiers: [{ up_to_kobo: 500_000, fee_kobo: 1_000 }, { up_to_kobo: 5_000_000, fee_kobo: 2_500 }, { up_to_kobo: null, fee_kobo: 5_000 }],
};

export interface FeeLine { kind: string; label: string; amount_kobo: number }

export function feeLines(amountKobo: number, rules: FeeRules = DEFAULT_FEES): FeeLine[] {
  const tier = rules.provider_tiers.find((t) => t.up_to_kobo === null || amountKobo <= t.up_to_kobo);
  const duty = rules.stamp_duty_kobo && amountKobo >= rules.stamp_duty_from_kobo ? rules.stamp_duty_kobo : 0;
  return [
    { kind: 'service', label: 'SpenDrip fee', amount_kobo: rules.service_kobo },
    { kind: 'provider', label: 'Transfer fee (Paystack)', amount_kobo: tier?.fee_kobo ?? 0 },
    { kind: 'stamp_duty', label: 'Stamp duty', amount_kobo: duty },
  ].filter((l) => l.amount_kobo > 0);
}

export const feeTotal = (amountKobo: number, rules?: FeeRules) => feeLines(amountKobo, rules).reduce((t, l) => t + l.amount_kobo, 0);

/** A group payout: SpenDrip's flat fee once, plus each transfer's own charge and stamp duty. Mirrors FeeSchedule.group_parts. */
export function groupFeeLines(amountsKobo: number[], rules: FeeRules = DEFAULT_FEES): FeeLine[] {
  let provider = 0, duty = 0;
  for (const a of amountsKobo) {
    const l = feeLines(a, rules);
    provider += l.find((x) => x.kind === 'provider')?.amount_kobo ?? 0;
    duty += l.find((x) => x.kind === 'stamp_duty')?.amount_kobo ?? 0;
  }
  return [
    { kind: 'service', label: 'SpenDrip fee (whole group)', amount_kobo: amountsKobo.length ? rules.group_service_kobo ?? 10_000 : 0 },
    { kind: 'provider', label: `Transfer fees (Paystack, ${amountsKobo.length} transfers)`, amount_kobo: provider },
    { kind: 'stamp_duty', label: 'Stamp duty', amount_kobo: duty },
  ].filter((l) => l.amount_kobo > 0);
}
export const groupFeeTotal = (amountsKobo: number[], rules?: FeeRules) => groupFeeLines(amountsKobo, rules).reduce((t, l) => t + l.amount_kobo, 0);
