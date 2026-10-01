export type Look = 'themed' | 'light' | 'dark';
export type Tint = 'cobalt' | 'sun' | 'hibiscus' | 'mint';

export interface FundingAccount { account_number: string; bank_name: string; account_name: string }

export interface Me {
  signed_in: boolean;
  dev_tools: boolean;
  locked?: boolean;
  signup?: { step: SignupStep; phone_masked?: string } | null;
  user?: {
    first_name: string; last_name: string; phone_masked: string; kyc_status: string; nin_last4: string;
    has_pin: boolean; pin_locked: boolean; has_face_id: boolean; look: Look; daily_cap_kobo: number | null; paused_all: boolean;
    notify_push: boolean; notify_whatsapp_recipients: boolean; notify_daily_summary: boolean; notify_low_balance: boolean;
    funding_account: FundingAccount | null;
  };
}
export type SignupStep = 'confirm' | 'document' | 'selfie' | 'otp' | 'pin';

export interface Recipient {
  id: number; label: string; is_self: boolean; bank_name: string; nip_bank_code: string; account_last4: string;
  verified_account_name: string; whatsapp: string; notify_whatsapp: boolean;
}

export type Frequency = 'daily' | 'weekly' | 'monthly';
export interface Plan {
  id: number; label: string; emoji: string; tint: Tint; amount_kobo: number; recipient: Recipient; frequency: Frequency;
  weekday: number | null; month_day: number | null; month_day_last: boolean; time_local: string; tz: string;
  starts_at: string; ends_at: string | null; status: 'active' | 'paused'; priority_rank: number | null; next_at: string | null;
}

export type EventStatus = 'protected' | 'send' | 'wait' | 'short' | 'cap' | 'sent' | 'waited' | 'failed' | 'missed' | 'paused' | 'sending' | 'scheduled';
export interface DripEvent { plan_id: number; at: string; amount_kobo: number; fee_kobo?: number; rank?: number | null; status: EventStatus }

export interface Summary {
  balance: { available_kobo: number; held_kobo: number; total_kobo: number };
  forecast: { window_end: string; protected_kobo: number; free_kobo: number; total_needed_kobo: number; top_up_kobo: number;
    priority_shortfall_kobo: number; events: DripEvent[] };
  fee_kobo: number;
  paused_all: boolean;
  funding_account: FundingAccount | null;
}

export interface Draft {
  label: string; emoji: string; tint: Tint; amount_kobo: number; recipient_id: number | null; frequency: Frequency;
  weekday: number; month_day: number; month_day_last: boolean; time_local: string; priority_rank: number;
}

export interface Preview {
  next_dates: string[]; runs_this_month: number; month_cost_kobo: number; fee_kobo: number; top_up_before_kobo: number;
  top_up_after_kobo: number; draft_waiting: number; priorities_short_after_kobo: number; priority_order: string[]; dropped_priorities: string[];
}

export interface ActivityItem {
  kind: 'run' | 'inflow'; status: string; at: string; amount_kobo: number; fee_kobo?: number; reason?: string; sender?: string;
  plan?: { id: number; label: string; emoji: string; tint: Tint };
  recipient?: { label: string; bank_name: string; account_last4: string };
  whatsapp?: { to: string; body: string; status: string } | null;
}
