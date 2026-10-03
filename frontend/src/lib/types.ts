export type Look = 'themed' | 'light' | 'dark' | 'auto';  // auto = time-aware: light by day, dark by night
export type ShownLook = Exclude<Look, 'auto'>;
export type Tint = 'cobalt' | 'sun' | 'hibiscus' | 'mint';

export interface FundingAccount { account_number: string; bank_name: string; account_name: string }

export interface Me {
  signed_in: boolean;
  dev_tools: boolean;
  locked?: boolean;
  signup?: { step: SignupStep; email_masked?: string } | null;
  user?: {
    first_name: string; last_name: string; email: string; email_masked: string; phone_masked: string;
    kyc_status: 'not_started' | 'bvn_pending' | 'nin_verified' | 'doc_uploaded' | 'verified' | 'rejected' | 'needs_review'; kyc_id_type: 'nin' | 'bvn';
    kyc_message: string; kyc_tier: number; kyc_mode: 'live' | 'mock'; bank_transfer_funding: boolean;
    limits: { max_balance_kobo: number; max_drip_kobo: number } | null;
    nin_last4: string; has_name: boolean;
    has_pin: boolean; pin_locked: boolean; has_face_id: boolean; look: Look; daily_cap_kobo: number | null; paused_all: boolean;
    notify_push: boolean; notify_whatsapp_recipients: boolean; notify_daily_summary: boolean; notify_low_balance: boolean; notify_email: boolean;
    funding_account: FundingAccount | null;
  };
}
export type SignupStep = 'code';

export interface Recipient {
  id: number; label: string; is_self: boolean; bank_name: string; nip_bank_code: string; account_last4: string;
  verified_account_name: string; whatsapp: string; notify_whatsapp: boolean;
}

export type Frequency = 'daily' | 'weekly' | 'monthly';
export interface PlanLine { id?: number; recipient: Recipient; amount_kobo: number; next_amount_kobo: number | null; skip_next: boolean }
export interface Plan {
  id: number; kind: 'single' | 'group'; label: string; emoji: string; tint: Tint; amount_kobo: number; fee_kobo: number;
  recipient: Recipient | null; lines: PlanLine[] | null; people?: number;
  next_payout?: { people: number; amount_kobo: number; fee_kobo: number; changed: boolean };
  frequency: Frequency;
  weekday: number | null; month_day: number | null; month_day_last: boolean; time_local: string; tz: string;
  starts_at: string; ends_at: string | null; status: 'active' | 'paused' | 'finished'; priority_rank: number | null; next_at: string | null;
  start_date: string; end_mode: EndMode; duration_months: number | null; end_date: string | null; finished_at: string | null;
  state: 'scheduled' | 'active' | 'paused' | 'finished'; first_drip_at: string | null; last_drip_at: string | null;
  total_drips: number | null; drips_done: number; total_cost_kobo: number | null;
}
export type EndMode = 'ongoing' | 'months' | 'date';

export type EventStatus = 'protected' | 'send' | 'wait' | 'short' | 'cap' | 'sent' | 'waited' | 'failed' | 'missed' | 'paused' | 'sending' | 'scheduled';
export interface DripEvent { plan_id: number; at: string; amount_kobo: number; fee_kobo?: number; rank?: number | null; status: EventStatus }

export interface FeeRules {
  service_kobo: number; group_service_kobo?: number; stamp_duty_kobo: number; stamp_duty_from_kobo: number;
  provider_tiers: { up_to_kobo: number | null; fee_kobo: number }[];
}
export interface FeeLineT { kind: string; label: string; amount_kobo: number }

export interface Summary {
  balance: { available_kobo: number; held_kobo: number; total_kobo: number };
  forecast: { window_end: string; protected_kobo: number; free_kobo: number; total_needed_kobo: number; top_up_kobo: number;
    priority_shortfall_kobo: number; events: DripEvent[] };
  fee_kobo: number;
  fees?: FeeRules;
  paused_all: boolean;
  funding_account: FundingAccount | null;
}

export interface DraftLine { recipient_id: number; amount_kobo: number; next_amount_kobo: number | null; skip_next: boolean }
export interface Draft {
  kind: 'single' | 'group'; lines: DraftLine[];
  label: string; emoji: string; tint: Tint; amount_kobo: number; recipient_id: number | null; frequency: Frequency;
  weekday: number; month_day: number; month_day_last: boolean; time_local: string; priority_rank: number;
  start_date: string; end_mode: EndMode; duration_months: number; end_date: string;
}

export interface Preview {
  next_dates: string[]; runs_this_month: number; month_cost_kobo: number; fee_kobo: number; fee_lines?: FeeLineT[]; top_up_before_kobo: number;
  top_up_after_kobo: number; draft_waiting: number; priorities_short_after_kobo: number; priority_order: string[]; dropped_priorities: string[];
  daily_cap_kobo?: number | null; over_daily_cap?: boolean;
  first_drip_at: string | null; last_drip_at: string | null; total_drips: number | null; total_amount_kobo: number | null; total_fees_kobo: number | null;
}

export interface ActivityPerson { label: string; bank_name: string; account_last4: string; amount_kobo: number; status: string }
export interface ActivityItem {
  kind: 'run' | 'inflow' | 'group'; people?: ActivityPerson[]; paid?: number; id?: string; retried?: boolean; is_retry?: boolean; status: string; at: string; amount_kobo: number; fee_kobo?: number; fee_lines?: FeeLineT[]; reason?: string; sender?: string;
  plan?: { id: number; label: string; emoji: string; tint: Tint };
  recipient?: { label: string; bank_name: string; account_last4: string };
  whatsapp?: { to: string; body: string; status: string } | null;
}
